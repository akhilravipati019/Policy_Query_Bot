import { useState } from 'react';
import { v4 as uuidv4 } from 'uuid';

const endpoint = import.meta.env.VITE_REACT_APP_API_URL_ENDPOINT;
const apiKey = import.meta.env.VITE_REACT_APP_API_KEY;

export default function ChatWindow({ chat, setChat, onNewChat }) {
    const [pdfFile, setPdfFile] = useState(null);
    const [question, setQuestion] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    async function submitQuestion(event) {
        event.preventDefault();
        const trimmedQuestion = question.trim();

        if (!pdfFile) {
            alert('Please select a PDF file.');
            return;
        }
        if (!trimmedQuestion) {
            alert('Please enter a question.');
            return;
        }

        const form = new FormData();
        form.append('file', pdfFile);
        form.append('question', trimmedQuestion);
        setIsLoading(true);

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { Authorization: `Bearer ${apiKey}` },
                body: form,
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || 'The server could not answer the question.');
            }

            setChat((previousChat) => ({
                id: previousChat?.id || uuidv4(),
                pdfIdentifier: previousChat?.pdfIdentifier || pdfFile.name,
                messages: [
                    ...(previousChat?.messages || []),
                    { sender: 'user', text: trimmedQuestion },
                    { sender: 'bot', text: data.answers?.[0] || 'No answer was returned.' },
                ],
            }));
            setQuestion('');
        } catch (error) {
            alert(error.message);
        } finally {
            setIsLoading(false);
        }
    }

    const hasMessages = Boolean(chat?.messages?.length);

    return (
        <div className="chat-window">
            <div className="header">
                <button onClick={onNewChat} className="new-chat-btn">+ New Chat</button>
            </div>
            <div className="messages">
                {chat?.messages.map((message, index) => (
                    <div key={index} className={`message ${message.sender}`}>
                        {message.text}
                    </div>
                ))}
                {isLoading && <div className="message bot">Reading the policy...</div>}
            </div>
            <form onSubmit={submitQuestion} className="input-form">
                <label className={`file-attach${hasMessages ? ' disabled' : ''}`}>
                    📎
                    <input
                        type="file"
                        accept="application/pdf"
                        disabled={hasMessages}
                        onChange={(event) => setPdfFile(event.target.files?.[0] || null)}
                    />
                </label>
                {pdfFile && <span className="file-name" title={pdfFile.name}>{pdfFile.name}</span>}
                <input
                    className="question-input"
                    type="text"
                    placeholder="Ask a question..."
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                />
                <button type="submit" disabled={isLoading}>Send</button>
            </form>
        </div>
    );
}
