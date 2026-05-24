const url = 'https://run.xcrawl.com/v1/scrape';
const options = {
  method: 'POST',
  headers: {
    Authorization: 'Bearer xc-VyoRhxnsnXt1c34F83qBeu4tv4OFxeac1HXw6RRpanNfAUBN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
      "url": "https://x.com",
      "mode": "sync",
      "proxy": {
            "location": "US"
      },
      "request": {
            "locale": "en-US",
            "device": "desktop",
            "only_main_content": false
      },
      "js_render": {
            "enabled": true
      },
      "output": {
            "formats": [
                  "markdown"
            ]
      }
})
};

try {
  const response = await fetch(url, options);
  const data = await response.json();
  console.log(data);
} catch (error) {
  console.error(error);
}