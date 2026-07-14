// Firestore 컬렉션/문서 상수
export const SETTINGS_COLLECTION = "system_settings";
export const SETTINGS_DOC = "general";
export const SYSTEM_CONTROL_COLLECTION = "system_control";
export const SYSTEM_CONTROL_DOC = "status";
export const DAILY_USAGE_COLLECTION = "daily_usage";

// Flask 백엔드 URL (환경변수에서 로드)
export const FLASK_SERVICE_URL = process.env.FLASK_SERVICE_URL || process.env.BACKEND_URL || "";
export const BACKEND_URL = process.env.BACKEND_URL || process.env.FLASK_SERVICE_URL || "";
