// src/utils/helpers.js

/**
 * Ensures we don't hold a reference to the user's live data
 * which could change before the buffer flushes.
 */
export const deepClone = (obj) => {
  try {
    return JSON.parse(JSON.stringify(obj));
  } catch (e) {
   
    return { ...obj };
  }
};

export const getTimestamp = () => new Date().toISOString();