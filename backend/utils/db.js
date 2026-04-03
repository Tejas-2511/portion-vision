const fs = require('fs').promises;
const path = require('path');

const DATA_DIR = path.join(__dirname, '..', 'data');
const FOOD_DB_PATH = path.join(DATA_DIR, 'foodDatabase.json');
const MENU_PATH = path.join(DATA_DIR, 'menu.json');

class Database {
    async ensureDataDir() {
        try {
            await fs.mkdir(DATA_DIR, { recursive: true });
        } catch (err) {
            if (err.code !== 'EEXIST') throw err;
        }
    }

    async getFoods() {
        try {
            if (!(await this.exists(FOOD_DB_PATH))) return [];
            const data = await fs.readFile(FOOD_DB_PATH, 'utf8');
            const foods = JSON.parse(data);
            return Array.isArray(foods) ? foods : [];
        } catch (err) {
            console.error('Database Error (getFoods):', err);
            return [];
        }
    }

    async saveFoods(foods) {
        try {
            await this.ensureDataDir();
            await fs.writeFile(FOOD_DB_PATH, JSON.stringify(foods, null, 2));
            return true;
        } catch (err) {
            console.error('Database Error (saveFoods):', err);
            return false;
        }
    }

    async getMenu() {
        try {
            if (!(await this.exists(MENU_PATH))) return null;
            const data = await fs.readFile(MENU_PATH, 'utf8');
            return JSON.parse(data);
        } catch (err) {
            console.error('Database Error (getMenu):', err);
            return null;
        }
    }

    async saveMenu(menu) {
        try {
            await this.ensureDataDir();
            await fs.writeFile(MENU_PATH, JSON.stringify(menu, null, 2));
            return true;
        } catch (err) {
            console.error('Database Error (saveMenu):', err);
            return false;
        }
    }

    async exists(filePath) {
        try {
            await fs.access(filePath);
            return true;
        } catch {
            return false;
        }
    }
}

module.exports = new Database();
