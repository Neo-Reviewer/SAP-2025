import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime
import socket
import platform
import psutil
import requests
import traceback

LOG_FILE = "linkedin_enhanced_footprints.json"
RAW_LOG_FILE = "linkedin_raw_logs.json"
captured_data = {"formatted": [], "raw": []}
start_time = datetime.utcnow()


async def save_log(log, formatted=True):
    try:
        if formatted:
            captured_data["formatted"].append(log)
        else:
            # Ensure the log is JSON serializable before adding to raw data
            # This handles any potential non-serializable objects
            json_serializable_log = ensure_json_serializable(log)
            captured_data["raw"].append(json_serializable_log)

        # Use safe JSON dump for both files
        with open(LOG_FILE, "w") as f:
            json.dump(captured_data["formatted"], f, indent=2, default=str)
        with open(RAW_LOG_FILE, "w") as f:
            json.dump(captured_data, f, indent=2, default=str)
    except Exception as e:
        print(f"Error saving log: {str(e)}")


def ensure_json_serializable(obj):
    """Recursively convert an object to be JSON serializable"""
    if isinstance(obj, dict):
        return {k: ensure_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [ensure_json_serializable(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        # Convert non-serializable objects to strings
        return str(obj)


async def log_request(req):
    try:
        post_data = await req.post_data() if req.method != "GET" else None
        # Handle potential binary data in post_data
        if post_data and not isinstance(post_data, str):
            try:
                post_data = post_data.decode('utf-8')
            except:
                post_data = f"<binary data of {len(post_data)} bytes>"

        # Convert headers to a safe dict
        headers_dict = dict(req.headers)

        await save_log({
            "type": "request",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "method": req.method,
            "url": req.url,
            "headers": headers_dict,
            "post_data": post_data
        }, formatted=False)
    except Exception as e:
        await save_log({
            "type": "error",
            "event": "request",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "error": str(e),
            "url": req.url if hasattr(req, 'url') else "unknown"
        }, formatted=False)


async def log_response(res):
    try:
        # Convert headers to a safe dict
        headers_dict = dict(res.headers)

        await save_log({
            "type": "response",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "status": res.status,
            "url": res.url,
            "headers": headers_dict
        }, formatted=False)
    except Exception as e:
        await save_log({
            "type": "error",
            "event": "response",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "error": str(e),
            "url": res.url if hasattr(res, 'url') else "unknown"
        }, formatted=False)


def get_location_info():
    try:
        response = requests.get('https://ipinfo.io/json', timeout=5)
        if response.status_code == 200:
            return response.json()
        return {"error": f"Failed to get location data: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def get_device_details():
    try:
        # System information
        system_info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "hostname": socket.gethostname(),
            "python_version": platform.python_version(),
        }

        # Hardware details
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        system_info.update({
            "total_ram": f"{memory.total / (1024 ** 3):.2f} GB",
            "available_ram": f"{memory.available / (1024 ** 3):.2f} GB",
            "ram_percent": f"{memory.percent}%",
            "cpu_cores": psutil.cpu_count(logical=True),
            "physical_cpu_cores": psutil.cpu_count(logical=False),
            "disk_total": f"{disk.total / (1024 ** 3):.2f} GB",
            "disk_free": f"{disk.free / (1024 ** 3):.2f} GB",
            "disk_percent": f"{disk.percent}%",
        })

        # Network details
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            system_info["local_ip"] = local_ip
        except:
            system_info["local_ip"] = "Unable to retrieve"

        return system_info
    except Exception as e:
        return {"error": str(e)}


async def safe_evaluate(page, script, description="evaluate script"):
    """Safely evaluate a script on the page with error handling"""
    try:
        if page.is_closed():
            print(f"Cannot {description}: page is closed")
            return {"error": "Page is closed"}

        result = await page.evaluate(script)
        return result
    except Exception as e:
        print(f"Error during {description}: {str(e)}")
        return {"error": str(e)}


async def log_system_resources():
    """Log system CPU and memory usage"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        await save_log({
            "type": "system_resources",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_gb": memory.used / (1024 ** 3)
        })
    except Exception as e:
        print(f"Error logging system resources: {str(e)}")


async def main():
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            # Log device details and IP/location at the beginning
            device_details = get_device_details()
            await save_log({
                "type": "device_info",
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "details": device_details
            })

            location_info = get_location_info()
            await save_log({
                "type": "location_info",
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "details": location_info
            })

            # Attach listeners
            page.on("request", lambda req: asyncio.create_task(log_request(req)))
            page.on("response", lambda res: asyncio.create_task(log_response(res)))

            # Custom user actions logger
            await page.expose_function("log_action", lambda action: asyncio.create_task(
                save_log({
                    "type": "user_action",
                    "timestamp": datetime.utcnow().isoformat() + 'Z',
                    **ensure_json_serializable(action)  # Ensure the action data is serializable
                })
            ))

            # Inject JS to capture scrolls, clicks, tab visibility, resource usage, and enhanced keystroke tracking
            await page.add_init_script("""
                (() => {
                    const debounce = (fn, wait) => {
                        let t;
                        return (...args) => {
                            clearTimeout(t);
                            t = setTimeout(() => fn(...args), wait);
                        };
                    };

                    document.addEventListener("click", e => {
                        try {
                            window.log_action({
                                event: "click",
                                tag: e.target.tagName,
                                text: e.target.innerText?.slice(0, 100) || "",
                                x: e.clientX,
                                y: e.clientY,
                                path: e.composedPath ? Array.from(e.composedPath()).map(el => el.tagName).join(' > ') : null
                            });
                        } catch(err) {
                            console.error("Error logging click:", err);
                        }
                    });

                    document.addEventListener("scroll", debounce(() => {
                        try {
                            window.log_action({
                                event: "scroll",
                                scrollY: window.scrollY,
                                scrollX: window.scrollX,
                                scrollHeight: document.documentElement.scrollHeight,
                                scrollPercentage: Math.round((window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100)
                            });
                        } catch(err) {
                            console.error("Error logging scroll:", err);
                        }
                    }, 1000));

                    document.addEventListener("visibilitychange", () => {
                        try {
                            window.log_action({
                                event: "tab_visibility",
                                state: document.visibilityState
                            });
                        } catch(err) {
                            console.error("Error logging visibility change:", err);
                        }
                    });

                    // Enhanced keystroke analytics
                    // Track timing patterns, field focus, and typing speed
                    let keystrokeData = {
                        keyCount: 0,
                        typingSessions: [],
                        currentSession: null,
                        lastKeystrokeTime: null,
                        intervals: [],
                        fieldTypes: {},
                        fieldFocusDuration: {}
                    };

                    // Track field focus time
                    document.addEventListener("focusin", (e) => {
                        try {
                            if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) {
                                const fieldId = e.target.id || e.target.name || 'unnamed_' + Math.random().toString(36).substring(7);
                                const fieldType = e.target.type || 'text';

                                keystrokeData.fieldTypes[fieldId] = fieldType;
                                keystrokeData.fieldFocusDuration[fieldId] = {
                                    startTime: Date.now(),
                                    type: fieldType,
                                    placeholder: e.target.placeholder || '',
                                    fieldTag: e.target.tagName
                                };

                                window.log_action({
                                    event: "field_focus",
                                    fieldId: fieldId,
                                    fieldType: fieldType,
                                    placeholder: e.target.placeholder || ''
                                });
                            }
                        } catch(err) {
                            console.error("Error logging field focus:", err);
                        }
                    });

                    document.addEventListener("focusout", (e) => {
                        try {
                            if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) {
                                const fieldId = e.target.id || e.target.name || 'unnamed_' + Math.random().toString(36).substring(7);

                                if (keystrokeData.fieldFocusDuration[fieldId]) {
                                    const duration = Date.now() - keystrokeData.fieldFocusDuration[fieldId].startTime;

                                    window.log_action({
                                        event: "field_blur",
                                        fieldId: fieldId,
                                        fieldType: keystrokeData.fieldTypes[fieldId] || 'unknown',
                                        focusDuration: duration,
                                        hasTyped: keystrokeData.keyCount > 0
                                    });

                                    delete keystrokeData.fieldFocusDuration[fieldId];
                                }
                            }
                        } catch(err) {
                            console.error("Error logging field blur:", err);
                        }
                    });

                    document.addEventListener("keydown", (e) => {
                        try {
                            // Start a new typing session if this is the first keystroke or if there was a long pause
                            const now = Date.now();
                            const isInputField = ['INPUT', 'TEXTAREA'].includes(e.target.tagName);
                            const fieldId = isInputField ? (e.target.id || e.target.name || 'unnamed_' + Math.random().toString(36).substring(7)) : null;

                            // Track typing session
                            if (!keystrokeData.currentSession || (now - keystrokeData.lastKeystrokeTime > 2000)) {
                                // If there was an existing session, save it first
                                if (keystrokeData.currentSession && keystrokeData.keyCount > 3) {
                                    keystrokeData.typingSessions.push({
                                        startTime: keystrokeData.currentSession,
                                        endTime: keystrokeData.lastKeystrokeTime || now,
                                        keyCount: keystrokeData.keyCount,
                                        avgInterval: keystrokeData.intervals.length ? 
                                            keystrokeData.intervals.reduce((a, b) => a + b, 0) / keystrokeData.intervals.length : 0,
                                        fieldType: keystrokeData.currentFieldType || 'unknown'
                                    });

                                    // Send completed typing session data
                                    if (keystrokeData.keyCount > 5) {
                                        window.log_action({
                                            event: "typing_session",
                                            duration: keystrokeData.lastKeystrokeTime - keystrokeData.currentSession,
                                            keyCount: keystrokeData.keyCount,
                                            field: isInputField ? e.target.tagName : 'OTHER',
                                            fieldType: keystrokeData.currentFieldType || 'unknown',
                                            avgInterval: keystrokeData.intervals.length ? 
                                                Math.round(keystrokeData.intervals.reduce((a, b) => a + b, 0) / keystrokeData.intervals.length) : 0,
                                        });
                                    }
                                }

                                // Start new session
                                keystrokeData.currentSession = now;
                                keystrokeData.keyCount = 0;
                                keystrokeData.intervals = [];
                                keystrokeData.currentFieldType = isInputField ? (e.target.type || 'text') : 'non-input';
                            }

                            // Calculate interval between keystrokes
                            if (keystrokeData.lastKeystrokeTime) {
                                const interval = now - keystrokeData.lastKeystrokeTime;
                                keystrokeData.intervals.push(interval);
                            }

                            keystrokeData.keyCount++;
                            keystrokeData.lastKeystrokeTime = now;

                            // Don't log every keystroke - instead log a pattern information every 10 keystrokes
                            if (keystrokeData.keyCount % 10 === 0) {
                                // Process the recent keystroke data
                                const recentIntervals = keystrokeData.intervals.slice(-10);
                                const avgInterval = recentIntervals.length ? 
                                    Math.round(recentIntervals.reduce((a, b) => a + b, 0) / recentIntervals.length) : 0;

                                window.log_action({
                                    event: "keystroke_pattern",
                                    field: isInputField ? e.target.tagName : 'OTHER',
                                    fieldId: fieldId,
                                    fieldType: isInputField ? (e.target.type || 'text') : 'non-input',
                                    avgInterval: avgInterval,
                                    typingSpeed: avgInterval > 0 ? Math.round(60000 / avgInterval / 5) : 0, // Estimate WPM
                                    pauseCount: recentIntervals.filter(i => i > 500).length,
                                    burstCount: recentIntervals.filter(i => i < 100).length
                                });
                            }
                        } catch(err) {
                            console.error("Error logging keystroke data:", err);
                        }
                    });

                    // Monitor keyboard input (simplified version kept for backward compatibility)
                    document.addEventListener("keydown", debounce((e) => {
                        try {
                            // Don't log actual keys for privacy, just the fact that typing happened
                            window.log_action({
                                event: "keyboard_input",
                                target: e.target.tagName,
                                isInputField: ['INPUT', 'TEXTAREA'].includes(e.target.tagName)
                            });
                        } catch(err) {
                            console.error("Error logging keyboard input:", err);
                        }
                    }, 1000));

                    // Log when page resources are loaded
                    window.addEventListener('load', () => {
                        try {
                            const resources = performance.getEntriesByType('resource');
                            const resourceTypes = {};

                            resources.forEach(resource => {
                                const type = resource.initiatorType;
                                if (!resourceTypes[type]) resourceTypes[type] = 0;
                                resourceTypes[type]++;
                            });

                            window.log_action({
                                event: "resources_loaded",
                                counts: resourceTypes,
                                total: resources.length
                            });
                        } catch(err) {
                            console.error("Error logging resources:", err);
                        }
                    });

                    // Performance monitoring
                    const perfInterval = setInterval(() => {
                        try {
                            const memoryData = performance.memory ? {
                                usedJSHeapSize: Math.round(performance.memory.usedJSHeapSize / (1024 * 1024)),
                                totalJSHeapSize: Math.round(performance.memory.totalJSHeapSize / (1024 * 1024))
                            } : null;

                            const timingData = performance.timing ? {
                                pageLoadTime: performance.timing.loadEventEnd - performance.timing.navigationStart
                            } : null;

                            window.log_action({
                                event: "performance_metrics",
                                memory: memoryData,
                                timing: timingData
                            });
                        } catch(err) {
                            console.error("Error logging performance:", err);
                            clearInterval(perfInterval);
                        }
                    }, 10000);
                })();
            """)

            # Open LinkedIn
            print("🔍 Navigating to LinkedIn...")
            await page.goto("https://www.linkedin.com/", timeout=60000)
            print("✅ LinkedIn page loaded. Enhanced logging has started.")

            # Wait for page to be fully loaded before continuing
            await page.wait_for_load_state("networkidle", timeout=60000)

            # Log permissions more comprehensively
            all_possible_permissions = [
                "geolocation", "notifications", "camera",
                "microphone", "background-sync", "persistent-storage",
                "midi", "clipboard-read", "clipboard-write", "payment-handler"
            ]

            # Request permissions
            for permission in all_possible_permissions:
                try:
                    await context.grant_permissions([permission])
                    print(f"✅ Requested permission: {permission}")
                except Exception as e:
                    print(f"❌ Failed to request permission {permission}: {e}")

            # Log actual permissions (with error handling)
            permission_script = """
                async () => {
                    const permissionsList = [
                        "geolocation", "notifications", "camera",
                        "microphone", "background-sync", "persistent-storage",
                        "midi", "clipboard-read", "clipboard-write", "payment-handler"
                    ];

                    const statuses = {};
                    for (const permission of permissionsList) {
                        try {
                            const status = await navigator.permissions.query({name: permission})
                                            .then(result => result.state);
                            statuses[permission] = status;
                        } catch (e) {
                            statuses[permission] = `error: ${e.message}`;
                        }
                    }
                    return statuses;
                }
            """

            permissions_status = await safe_evaluate(page, permission_script, "check permissions")

            await save_log({
                "type": "permissions_status",
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "statuses": permissions_status
            })

            # Log media devices (with error handling)
            media_script = """
                async () => {
                    try {
                        const devices = await navigator.mediaDevices.enumerateDevices();
                        return devices.map(device => ({
                            kind: device.kind,
                            label: device.label,
                            deviceId: device.deviceId.substring(0, 8) + '...' // truncate for privacy
                        }));
                    } catch (e) {
                        return {error: e.message};
                    }
                }
            """

            media_devices = await safe_evaluate(page, media_script, "get media devices")

            await save_log({
                "type": "media_devices",
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "devices": media_devices
            })

            # Service Workers (with error handling)
            sw_script = "navigator.serviceWorker.getRegistrations().then(r => r.map(x => x.scope))"
            sws = await safe_evaluate(page, sw_script, "check service workers")

            await save_log({
                "type": "service_workers",
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "registered_scopes": sws
            })

            # Cache Data (with error handling)
            cache_script = """
                caches.keys().then(keys =>
                    Promise.all(keys.map(k =>
                        caches.open(k).then(c =>
                            c.keys().then(reqs => reqs.map(r => r.url))
                        )
                    )).then(r => [].concat(...r))
                ).catch(e => ({error: e.message}))
            """

            cached_urls = await safe_evaluate(page, cache_script, "check cache data")

            await save_log({
                "type": "cache_data",
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "cached_urls": cached_urls
            })

            # Periodically log CPU and Memory usage
            print("Starting periodic resource logging...")
            for i in range(6):  # Log every 10 seconds for 60 seconds
                if page.is_closed():
                    print("Page closed, stopping resource logging")
                    break

                await log_system_resources()
                print(f"Logged system resources ({i + 1}/6)")

                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    print("Resource logging interrupted")
                    break

            # Only try to close if browser is still open
            if browser and not browser.is_connected():
                print("Browser already disconnected")
            else:
                # Log session time
                duration = (datetime.utcnow() - start_time).total_seconds()
                await save_log({
                    "type": "session_summary",
                    "timestamp": datetime.utcnow().isoformat() + 'Z',
                    "session_duration_seconds": duration,
                    "requests_count": len([r for r in captured_data["raw"] if r.get("type") == "request"]),
                    "responses_count": len([r for r in captured_data["raw"] if r.get("type") == "response"])
                })

                print("Closing browser...")
                await browser.close()
                print("✅ Enhanced logging complete. Check the output JSON files.")

    except Exception as e:
        print(f"Error in main function: {str(e)}")
        print(traceback.format_exc())

        # Try to close browser if it exists and is still connected
        if browser and browser.is_connected():
            try:
                await browser.close()
                print("Browser closed after error")
            except Exception as close_error:
                print(f"Error closing browser: {str(close_error)}")

        # Save final error log
        await save_log({
            "type": "fatal_error",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "error": str(e),
            "traceback": traceback.format_exc()
        })


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Script interrupted by user")
    except Exception as e:
        print(f"Unhandled exception: {str(e)}")
        print(traceback.format_exc())