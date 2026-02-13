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

    // Load data from localStorage on mount
    useEffect(() => {
        try {
            const profile = localStorage.getItem('userProfile');
            if (profile) {
                setUserProfile(JSON.parse(profile));
            }

            const menu = localStorage.getItem('todaysMenu');
            if (menu) {
                setTodaysMenu(JSON.parse(menu));
            }
        } catch (error) {
            console.error('Error loading data from localStorage:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    // Sync userProfile to localStorage whenever it changes
    useEffect(() => {
        if (userProfile) {
            try {
                localStorage.setItem('userProfile', JSON.stringify(userProfile));
            } catch (error) {
                console.error('Error saving user profile:', error);
            }
        }
    }, [userProfile]);

    // Sync todaysMenu to localStorage whenever it changes
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
