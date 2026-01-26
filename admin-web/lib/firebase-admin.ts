import * as admin from 'firebase-admin';

// Lazy getter functions that initialize on first access
let _db: admin.firestore.Firestore | null = null;
let _auth: admin.auth.Auth | null = null;

export const getDb = () => {
  if (!_db) {
    if (!admin.apps.length) {
      const credentialsJson = process.env.GOOGLE_APPLICATION_CREDENTIALS_JSON_BASE64;
      try {
        if (credentialsJson) {
          const decoded = Buffer.from(credentialsJson, 'base64').toString('utf-8');
          const serviceAccount = JSON.parse(decoded);
          admin.initializeApp({
            credential: admin.credential.cert(serviceAccount),
            projectId: process.env.FIRESTORE_PROJECT_ID,
          });
        } else {
          admin.initializeApp({
            projectId: process.env.FIRESTORE_PROJECT_ID,
          });
        }
      } catch (error) {
        console.error('Firebase Admin initialization failed:', error);
        throw error;
      }
    }
    _db = admin.firestore();
  }
  return _db;
};

export const getAuth = () => {
  if (!_auth) {
    if (!admin.apps.length) {
      const credentialsJson = process.env.GOOGLE_APPLICATION_CREDENTIALS_JSON_BASE64;
      try {
        if (credentialsJson) {
          const decoded = Buffer.from(credentialsJson, 'base64').toString('utf-8');
          const serviceAccount = JSON.parse(decoded);
          admin.initializeApp({
            credential: admin.credential.cert(serviceAccount),
            projectId: process.env.FIRESTORE_PROJECT_ID,
          });
        } else {
          admin.initializeApp({
            projectId: process.env.FIRESTORE_PROJECT_ID,
          });
        }
      } catch (error) {
        console.error('Firebase Admin initialization failed:', error);
        throw error;
      }
    }
    _auth = admin.auth();
  }
  return _auth;
};
