// src/components/App.js
import React, { useState } from 'react';
import ChatWindow from './ChatWindow.jsx';
import '../App.css'; // This will link to your main stylesheet

const App = () => {
    // We only need to manage the current chat state now
    const [currentChat, setCurrentChat] = useState(null);

    // This function will be called to start a new chat, clearing the old one
    const startNewChat = () => {
        setCurrentChat(null);
    };

    return (
        <div className="app-container">
            <ChatWindow 
                currentChat={currentChat} 
                setCurrentChat={setCurrentChat}
                startNewChat={startNewChat}
            />
        </div>
    );
};

export default App;