self.addEventListener("install", (event) => {
    console.log('install xeus-python service');
    event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
    console.log('activate xeus-python service');
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
    var url = new URL(event.request.url);
    if (url.pathname === '/SLEEP') {
        console.log('SLEEP', event);

        // wait ?t=X seconds, then return a 304:
        event.respondWith(new Promise(resolve => {
            var t = Number.parseFloat(new URLSearchParams(url.search).get('t')) * 1000.;
            var response = new Response(null, { status: 304 });

            setTimeout(resolve, t, response);
        }));
    }
});
