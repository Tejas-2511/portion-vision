import { createContext, useContext, useState, useEffect } from 'react';
import api from "../services/api";

const AppContext = createContext();

/**
 * Global state provider for PortionVision
 * Manages user profile, menu data, and food database with localStorage sync
 */
export function AppProvider({ children }) {
    const [userProfile, setUserProfile] = useState(null);
    const [todaysMenu, setTodaysMenu] = useState(null);
    const [loading, setLoading] = useState(true);

    // Load data from server & localStorage on mount
    useEffect(() => {
        const loadDocs = async () => {
            try {
                // 1. Load from LocalStorage first (for instant paint)
                const localProfile = localStorage.getItem('userProfile');
                const localMenu = localStorage.getItem('todaysMenu');

                const localProfileObj = localProfile ? JSON.parse(localProfile) : null;
                const localMenuObjRaw = localMenu ? JSON.parse(localMenu) : null;

                const localMenuItems = Array.isArray(localMenuObjRaw?.items)
                    ? localMenuObjRaw.items
                    : Array.isArray(localMenuObjRaw?.menuItems)
                        ? localMenuObjRaw.menuItems
                        : [];

                const localMenuObj = localMenuObjRaw
                    ? {
                        ...localMenuObjRaw,
                        items: localMenuItems,
                        text: typeof localMenuObjRaw.text === 'string'
                            ? localMenuObjRaw.text
                            : localMenuItems.length
                                ? localMenuItems.join('\n')
                                : '',
                    }
                    : null;

                if (localProfileObj) setUserProfile(localProfileObj);
                if (localMenuObj) setTodaysMenu(localMenuObj);

                // 2. Fetch latest Menu from Server (Sync)
                // Profile is now LocalStorage only
                const serverMenu = await api.getMenu();

                if (serverMenu?.items?.length) {
                    // Merge server menu into local menu (preserve client-only fields like mealType)
                    setTodaysMenu((prev) => {
                        const prevMenu = prev || localMenuObj || null;
                        if (!prevMenu) return serverMenu;

                        return {
                            ...prevMenu,
                            ...serverMenu,
                            mealType: prevMenu.mealType ?? serverMenu.mealType,
                        };
                    });
                }

            } catch (error) {
                console.error('Error syncing data:', error);
            } finally {
                setLoading(false);
            }
        };

        loadDocs();
    }, []);

    // Sync userProfile to LocalStorage (Server sync removed)
    useEffect(() => {
        if (userProfile) {
            try {
                localStorage.setItem('userProfile', JSON.stringify(userProfile));
            } catch (error) {
                console.error('Error saving user profile:', error);
            }
        }
    }, [userProfile]);

    // Sync todaysMenu to LocalStorage only (Server update happens via Upload)
    useEffect(() => {
        if (todaysMenu) {
            try {
                localStorage.setItem('todaysMenu', JSON.stringify(todaysMenu));
            } catch (error) {
                console.error('Error saving menu:', error);
            }
        }
    }, [todaysMenu]);

    const value = {
        userProfile,
        setUserProfile,
        todaysMenu,
        setTodaysMenu,
        loading,
    };

    return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

/**
 * Hook to access app context
 * @returns {object} App context value
 */
export function useApp() {
    const context = useContext(AppContext);
    if (!context) {
        throw new Error('useApp must be used within AppProvider');
    }
    return context;
}
