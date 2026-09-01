import React, { useState } from 'react';
import { v4 as uuidv4 } from 'uuid';

const ChatWindow = ({ currentChat, setCurrentChat, startNewChat }) => {
    const [pdfFile, setPdfFile] = useState(null);
    const [question, setQuestion] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const API_URL_ENDPOINT = import.meta.env.VITE_REACT_APP_API_URL_ENDPOINT;
    const API_KEY = import.meta.env.VITE_REACT_APP_API_KEY;

    const handleSubmit = async (e) => {
        e.preventDefault();

        // Validate the form inputs
        if (!pdfFile) {
            alert("Please select a PDF file.");
            return;
        }
        if (!question.trim()) {
            alert("Please enter a question before sending.");
            return;
        }

        setIsLoading(true);

        const endpoint = API_URL_ENDPOINT;
        const headers = {
            'Authorization': `Bearer ${API_KEY}`,
        };
        const body = new FormData();
        body.append('file', pdfFile);
        body.append('question', question);

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers,
                body,
            });

            if (!response.ok) {
                throw new Error('Failed to fetch response from backend.');
            }

            const data = await response.json();
            const newAnswer = data.answers[0];
            const chatMessage = { sender: 'user', text: question };
            const botMessage = { sender: 'bot', text: newAnswer };

            setCurrentChat(prevChat => ({
                id: prevChat ? prevChat.id : uuidv4(),
                messages: [...(prevChat?.messages || []), chatMessage, botMessage],
                pdfIdentifier: prevChat?.pdfIdentifier || pdfFile.name,
            }));

            setQuestion('');
        } catch (error) {
            console.error('Error:', error);
        } finally {
            setIsLoading(false);
        }
    };
    
    const chatInProgress = currentChat && currentChat.messages.length > 0;

    return (
        <div className="chat-window">
            <div className="header">
                <button onClick={startNewChat} className="new-chat-btn">
                    + New Chat
                </button>
            </div>
            <div className="messages">
                {currentChat && currentChat.messages.map((msg, index) => (
                    <div key={index} className={`message ${msg.sender}`}>
                        {msg.text}
                    </div>
                ))}
                {isLoading && <div className="message bot">Loading...</div>}
            </div>
            
            <form onSubmit={handleSubmit} className="input-form">
                <label className={`file-attach${chatInProgress ? ' disabled' : ''}`}>
                    📎
                    <input
                        type="file"
                        accept="application/pdf"
                        onChange={(e) => setPdfFile(e.target.files[0])}
                        disabled={chatInProgress}
                    />
                </label>
                {pdfFile && <span className="file-name" title={pdfFile.name}>{pdfFile.name}</span>}
                <input
                    type="text"
                    className="question-input"
                    placeholder="Ask a question..."
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                />
                <button type="submit" disabled={isLoading}>Send</button>
            </form>
        </div>
    );
};

export default ChatWindow;