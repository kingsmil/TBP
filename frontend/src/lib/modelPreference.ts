const MODEL_KEY = "homeos_selected_model";

export function getStoredModel(): string | null {
  try {
    return localStorage.getItem(MODEL_KEY);
  } catch {
    return null;
  }
}

export function setStoredModel(model: string): void {
  try {
    localStorage.setItem(MODEL_KEY, model);
  } catch {
    // ignore
  }
}

export function clearStoredModel(): void {
  try {
    localStorage.removeItem(MODEL_KEY);
  } catch {
    // ignore
  }
}
