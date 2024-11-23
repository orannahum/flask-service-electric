const functions = require('firebase-functions');
const admin = require('firebase-admin');
const express = require('express');
const path = require('path');

// Initialize Firebase Admin SDK
admin.initializeApp();

// Create an Express app for the Flask app
const app = express();

// Set up the static files and template directory
app.use(express.static(path.join(__dirname, 'public')));
app.set('views', path.join(__dirname, 'templates'));

// Route for the Flask app
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

exports.app = functions.https.onRequest(app);
