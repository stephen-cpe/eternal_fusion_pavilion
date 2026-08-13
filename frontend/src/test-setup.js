// Vitest global setup — registers jest-dom matchers and stubs the browser APIs
// that the app expects (matchMedia, IntersectionObserver, etc.) under jsdom.
import "@testing-library/jest-dom";

// jsdom does not implement matchMedia; ThemeProvider and other components may
// read it. Provide a no-op stub.
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

// react-toastify mounts a portal that references scroll/animation APIs not
// present in jsdom. Keep these stubs minimal and permissive.
window.scrollTo = window.scrollTo || (() => {});