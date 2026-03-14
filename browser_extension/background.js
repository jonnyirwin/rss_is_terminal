// Toggle the in-page panel when the extension icon is clicked
chrome.action.onClicked.addListener(async (tab) => {
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ["content.js"],
  });
  chrome.tabs.sendMessage(tab.id, { action: "togglePanel" });
});

// Relay native messaging requests from content script
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "nativeSave") {
    chrome.runtime.sendNativeMessage(
      "rss_is_terminal",
      { action: "save", config: msg.config, category_ids: msg.category_ids },
      (response) => {
        if (chrome.runtime.lastError) {
          sendResponse({
            error: chrome.runtime.lastError.message,
            nativeNotInstalled: true,
          });
        } else {
          sendResponse(response);
        }
      }
    );
    return true; // async response
  }

  if (msg.action === "nativeGetCategories") {
    chrome.runtime.sendNativeMessage(
      "rss_is_terminal",
      { action: "get_categories" },
      (response) => {
        if (chrome.runtime.lastError) {
          sendResponse({ categories: [] });
        } else {
          sendResponse(response);
        }
      }
    );
    return true;
  }

  if (msg.action === "nativeAddFeed") {
    chrome.runtime.sendNativeMessage(
      "rss_is_terminal",
      { action: "add_feed", url: msg.url, title: msg.title, category_ids: msg.category_ids },
      (response) => {
        if (chrome.runtime.lastError) {
          sendResponse({
            error: chrome.runtime.lastError.message,
            nativeNotInstalled: true,
          });
        } else {
          sendResponse(response);
        }
      }
    );
    return true;
  }

  if (msg.action === "nativePing") {
    chrome.runtime.sendNativeMessage(
      "rss_is_terminal",
      { action: "ping" },
      (response) => {
        if (chrome.runtime.lastError) {
          sendResponse({ available: false, error: chrome.runtime.lastError.message });
        } else {
          sendResponse({ available: true, ...response });
        }
      }
    );
    return true;
  }
});
