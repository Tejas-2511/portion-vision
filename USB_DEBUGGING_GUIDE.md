# USB Debugging Port Forwarding - Quick Guide

## Prerequisites
✅ Servers running (already done!)
- Frontend: `npm run dev -- --host` (port 5173)
- Backend: `npm run dev -- --host` (port 5000)

## Setup Steps

### 1. Enable USB Debugging on Your Phone
1. Settings → About Phone → Tap "Build Number" 7 times
2. Settings → Developer Options → Enable "USB Debugging"

### 2. Connect Phone via USB
1. Plug phone into computer
2. Allow USB debugging when prompted on phone
3. Check "Always allow from this computer"

### 3. Verify Connection
```powershell
adb devices
```
You should see your device listed like:
```
List of devices attached
ABC123XYZ    device
```

### 4. Forward Ports
Run these commands to forward both frontend and backend:

```powershell
# Forward frontend (port 5173)
adb reverse tcp:5173 tcp:5173

# Forward backend (port 5000)
adb reverse tcp:5000 tcp:5000
```

You should see:
```
5173
5000
```

### 5. Access on Phone
Open Chrome on your phone and go to:
```
http://localhost:5173
```

The app will work exactly as if it were running on your phone!

### 6. Remote Debugging (Optional)
On your computer, open Chrome and go to:
```
chrome://inspect/#devices
```

Click "Inspect" under your phone's Chrome tab to see:
- Console logs
- Network requests
- Service worker status
- PWA manifest

## Testing PWA Features

Once the app is open on your phone:

1. **Test camera**: Click "📸 Take Photo" - camera should open
2. **Install PWA**: 
   - Chrome menu (⋮) → "Install app" or "Add to Home Screen"
   - Or Safari: Share (□↑) → "Add to Home Screen"
3. **Launch installed app**: Tap icon on home screen
4. **Test offline**: 
   - Turn on airplane mode
   - App should still load (cached assets)

## Troubleshooting

**Device not showing in `adb devices`?**
- Ensure USB debugging is enabled on phone
- Try a different USB cable
- Re-accept the USB debugging prompt
- Restart ADB: `adb kill-server` then `adb start-server`

**Connection keeps dropping?**
- Disable "USB debugging timeout" in Developer Options (if available)
- Keep phone unlocked during testing

**Backend not connecting?**
- Verify backend is running on port 5000
- Check both port forwards are active: `adb reverse --list`
- Make sure your code uses `http://localhost:5000` (not an IP address)

**Remove port forwarding:**
```powershell
adb reverse --remove-all
```

## Quick Commands Reference

```powershell
# Check connected devices
adb devices

# Forward frontend
adb reverse tcp:5173 tcp:5173

# Forward backend  
adb reverse tcp:5000 tcp:5000

# List active forwards
adb reverse --list

# Remove all forwards
adb reverse --remove-all

# Restart ADB
adb kill-server
adb start-server
```

---

**You're ready to test!** 🚀

Once you run the port forwarding commands, open `http://localhost:5173` on your phone's Chrome browser.
