import { createContext, useContext, useState, useEffect } from 'react';

const AppContext = createContext();

/**
 * Global state provider for PortionVision
 * Manages user profile, menu data, and food database with localStorage sync
 */
export function AppProvider({ children }) {
    const [userProfile, setUserProfile] = useState(null);
    const [todaysMenu, setTodaysMenu] = useState(null);
    const [foodDatabase, setFoodDatabase] = useState([]);
    const [loading, setLoading] = useState(true);

    // Load data from server & localStorage on mount
    useEffect(() => {
        const loadDocs = async () => {
            try {
                // 1. Load from LocalStorage first (for instant paint)
                const localProfile = localStorage.getItem('userProfile');
                const localMenu = localStorage.getItem('todaysMenu');

                if (localProfile) setUserProfile(JSON.parse(localProfile));
                if (localMenu) setTodaysMenu(JSON.parse(localMenu));

                // 2. Fetch latest Menu from Server (Sync)
                // Profile is now LocalStorage only
                const serverMenu = await api.getMenu();

                if (serverMenu) {
                    // console.log("Synced Menu from Server:", serverMenu);
                    setTodaysMenu(serverMenu);
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
        foodDatabase,
        setFoodDatabase,
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
