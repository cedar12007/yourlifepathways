/**
 * YourLifePathways - Visitor Attention & Scroll Telemetry
 * Captures real scroll depth (%) and active attention/dwell time per section.
 * Lightweight, zero dependencies, uses Beacon API for zero page lag.
 */
(function () {
    // Only track if running in browser and not inside an iframe or admin dashboard
    if (typeof window === 'undefined' || window.self !== window.top) return;
    if (window.location.pathname.startsWith('/admin')) return;

    var maxScrollDepth = 0;
    var currentSection = null;
    var sectionStartTime = Date.now();
    var pendingDwell = {}; // Accumulated dwell time per section in seconds
    var lastSentTime = 0;
    var sentMilestones = new Set();

    function getScrollDepth() {
        var docHeight = document.documentElement.scrollHeight - window.innerHeight;
        if (docHeight <= 0) return 100;
        var scrollY = window.scrollY || window.pageYOffset || 0;
        return Math.min(100, Math.max(0, Math.round((scrollY / docHeight) * 100)));
    }

    function flushTelemetry(force) {
        var now = Date.now();
        // Record current section if active
        if (currentSection) {
            var elapsed = Math.round((now - sectionStartTime) / 1000);
            if (elapsed >= 3) {
                pendingDwell[currentSection] = (pendingDwell[currentSection] || 0) + elapsed;
                sectionStartTime = now;
            }
        }

        var depth = getScrollDepth();
        if (depth > maxScrollDepth) {
            maxScrollDepth = depth;
        }

        var hasDwell = Object.keys(pendingDwell).length > 0;
        if (!force && !hasDwell && (now - lastSentTime < 5000)) {
            return;
        }

        var params = new URLSearchParams();
        params.append('url', window.location.href.split('#')[0]);
        params.append('depth', maxScrollDepth);
        params.append('_cb', now);

        if (hasDwell) {
            // Format sections into a compact string: "intro:12,cost:45,contact:20"
            var parts = [];
            for (var sec in pendingDwell) {
                if (pendingDwell.hasOwnProperty(sec) && pendingDwell[sec] >= 3) {
                    parts.push(sec + ':' + pendingDwell[sec]);
                }
            }
            if (parts.length > 0) {
                params.append('sections', parts.join(','));
            }
            pendingDwell = {}; // Reset pending
        }

        lastSentTime = now;
        var endpoint = '/log_telemetry?' + params.toString();

        if (navigator.sendBeacon) {
            navigator.sendBeacon(endpoint);
        } else {
            fetch(endpoint, { method: 'GET', keepalive: true }).catch(function () {});
        }
    }

    // Scroll listener with throttle
    var scrollTimer = null;
    window.addEventListener('scroll', function () {
        if (!scrollTimer) {
            scrollTimer = setTimeout(function () {
                scrollTimer = null;
                var depth = getScrollDepth();
                if (depth > maxScrollDepth) {
                    maxScrollDepth = depth;
                    [25, 50, 75, 90].forEach(function (m) {
                        if (maxScrollDepth >= m && !sentMilestones.has(m)) {
                            sentMilestones.add(m);
                            flushTelemetry(false);
                        }
                    });
                }
            }, 300);
        }
    }, { passive: true });

    // Section Attention Observer (IntersectionObserver)
    if ('IntersectionObserver' in window) {
        var sectionObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting && entry.intersectionRatio >= 0.25) {
                    var secId = entry.target.id;
                    if (secId && secId !== currentSection) {
                        // Leaving previous section
                        if (currentSection) {
                            var elapsed = Math.round((Date.now() - sectionStartTime) / 1000);
                            if (elapsed >= 3) {
                                pendingDwell[currentSection] = (pendingDwell[currentSection] || 0) + elapsed;
                            }
                        }
                        // Entering new section
                        currentSection = secId;
                        sectionStartTime = Date.now();
                    }
                }
            });
        }, { threshold: [0.25, 0.5] });

        document.addEventListener('DOMContentLoaded', function () {
            // Observe main page sections and blog articles
            var targets = document.querySelectorAll('section[id], article[id], #post-content, #comments');
            targets.forEach(function (el) {
                sectionObserver.observe(el);
            });
        });
    }

    // Send on visibility change (leaving tab or closing browser)
    document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'hidden') {
            flushTelemetry(true);
        }
    });

    window.addEventListener('pagehide', function () {
        flushTelemetry(true);
    });
})();

