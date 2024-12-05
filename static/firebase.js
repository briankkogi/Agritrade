
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js";
import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-auth.js";
import { getFirestore, collection, addDoc, getDocs, doc, deleteDoc, updateDoc, serverTimestamp, query, where, getDoc } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-firestore.js";

const firebaseConfig = {
    apiKey: "AIzaSyAC0as_uoSjFWaQNEZAI_wtK1kqYAReF-0",
    authDomain: "agritrade-3fe65.firebaseapp.com",
    databaseURL: "https://agritrade-3fe65-default-rtdb.firebaseio.com",
    projectId: "agritrade-3fe65",
    storageBucket: "agritrade-3fe65.appspot.com",
    messagingSenderId: "742671449846",
    appId: "1:742671449846:web:2bd6f4b4cd0772bee6b6d7",
    measurementId: "G-5NSK9449FG"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

let currentUser = null;

// Display user info and load inventory
onAuthStateChanged(auth, async (user) => {
    if (user) {
        console.log(user.uid);
        currentUser = user;
        
        // Fetch user's full name from Firestore
        const userDocRef = doc(db, "users", user.uid);
        const userDocSnap = await getDoc(userDocRef);
        
        if (userDocSnap.exists()) {
            const userData = userDocSnap.data();
            const fullName = userData.fullName || "User";
            document.getElementById('user-info').textContent = fullName;
        } else {
            console.log("No user document found!");
            document.getElementById('user-info').textContent = "User";
        }
        
        loadInventory();
        loadsoldItems();
    } else {
        console.error("No user is signed in.");
        window.location.href = "/login";
    }
});