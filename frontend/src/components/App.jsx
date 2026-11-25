import { useState } from 'react';
import ChatWindow from './ChatWindow.jsx';
import '../App.css';

export default function App() {
    const [chat, setChat] = useState(null);

    return (
        <div className="app-container">
            <ChatWindow chat={chat} setChat={setChat} onNewChat={() => setChat(null)} />
        </div>
    );
}
