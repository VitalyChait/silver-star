"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./chatbot.module.css";
import "../globals.css";

type Message = {
  id: string;
  text: string;
  sender: "user" | "bot";
  timestamp: Date;
};

type CandidateInfo = {
  name?: string | null;
  location?: string | null;
  looking_for?: string | null;
  skills?: string | null;
  availability?: string | null;
};

export default function ChatbotPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [candidateInfo, setCandidateInfo] = useState<CandidateInfo>({});
  const [error, setError] = useState<string | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Scroll to the bottom of messages when new messages are added
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Initialize conversation on component mount
  useEffect(() => {
    // Generate a unique conversation ID
    const id = `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setConversationId(id);
    
    // Add initial bot greeting message directly instead of sending "Hi" and getting a response
    const botGreeting: Message = {
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}_bot`,
      text: "Hello there! Welcome to Silver Star. I'm your job recruitment assistant. To get started, could you please tell me your name?",
      sender: "bot",
      timestamp: new Date(),
    };
    
    setMessages([botGreeting]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSendMessage = async (text: string) => {
    if (!text.trim()) return;
    
    // Add user message to the chat
    const userMessage: Message = {
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}_user`,
      text: text.trim(),
      sender: "user",
      timestamp: new Date(),
    };
    
    setMessages((prev) => [...prev, userMessage]);
    setInputText("");
    setIsLoading(true);
    setError(null);
    
    try {
      // Send message to the backend
      const response = await fetch("http://localhost:8000/api/chatbot/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: text.trim(),
          conversation_id: conversationId,
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Failed: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Add bot response to the chat
      const botMessage: Message = {
        id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}_bot`,
        text: data.response,
        sender: "bot",
        timestamp: new Date(),
      };
      
      setMessages((prev) => [...prev, botMessage]);
      setCandidateInfo(data.candidate_info);
    } catch (e: any) {
      setError(e.message || "Error sending message");
      
      // Add error message to the chat
      const errorMessage: Message = {
        id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}_error`,
        text: "Sorry, I'm having trouble responding right now. Please try again later.",
        sender: "bot",
        timestamp: new Date(),
      };
      
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleVoiceRecord = async () => {
    if (isRecording) {
      // Stop recording
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop();
      }
      setIsRecording(false);
      return;
    }
    
    try {
      // Start recording
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.onstop = async () => {
        // Combine audio chunks into a single blob
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        
        // Convert to base64
        const reader = new FileReader();
        reader.onloadend = async () => {
          const base64Audio = reader.result as string;
          
          // Add user message to indicate voice input
          const userMessage: Message = {
            id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}_user_voice`,
            text: "🎤 Voice message",
            sender: "user",
            timestamp: new Date(),
          };
          
          setMessages((prev) => [...prev, userMessage]);
          setIsLoading(true);
          setError(null);
          
          try {
            // Send voice message to the backend
            const response = await fetch("http://localhost:8000/api/chatbot/voice", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                audio_data: base64Audio.split(",")[1], // Remove the data:audio/webm;base64, prefix
                conversation_id: conversationId,
              }),
            });
            
            if (!response.ok) {
              throw new Error(`Failed: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Add bot response to the chat
            const botMessage: Message = {
              id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}_bot`,
              text: data.response_text,
              sender: "bot",
              timestamp: new Date(),
            };
            
            setMessages((prev) => [...prev, botMessage]);
            setCandidateInfo(data.candidate_info);
            
            // Play the audio response
            if (data.response_audio && data.response_audio !== "This is a placeholder for text-to-speech conversion") {
              const audio = new Audio(`data:audio/mp3;base64,${data.response_audio}`);
              audio.play().catch((e) => {
                console.error("Error playing audio:", e);
              });
            }
          } catch (e: any) {
            setError(e.message || "Error processing voice message");
            
            // Add error message to the chat
            const errorMessage: Message = {
              id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}_error`,
              text: "Sorry, I'm having trouble understanding your voice message. Please try again or use text input.",
              sender: "bot",
              timestamp: new Date(),
            };
            
            setMessages((prev) => [...prev, errorMessage]);
          } finally {
            setIsLoading(false);
          }
        };
        
        reader.readAsDataURL(audioBlob);
      };
      
      mediaRecorder.start();
      setIsRecording(true);
    } catch (e: any) {
      setError(e.message || "Error accessing microphone");
      setIsRecording(false);
    }
  };

  const handleResetConversation = async () => {
    try {
      await fetch("http://localhost:8000/api/chatbot/reset", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          conversation_id: conversationId,
        }),
      });
      
      // Reset local state
      setMessages([]);
      setCandidateInfo({});
      setError(null);
      
      // Generate a new conversation ID
      const id = `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      setConversationId(id);
      
      // Add initial bot greeting message directly instead of sending "Hi" and getting a response
      const botGreeting: Message = {
        id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}_bot`,
        text: "Hello there! Welcome to Silver Star. I'm your job recruitment assistant. To get started, could you please tell me your name?",
        sender: "bot",
        timestamp: new Date(),
      };
      
      setMessages([botGreeting]);
    } catch (e: any) {
      setError(e.message || "Error resetting conversation");
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSendMessage(inputText);
  };

  return (
    <main className={styles.chatbotContainer}>
      <header className={styles.chatbotHeader}>
        <h1>Silver Star Job Assistant</h1>
        <p>I'm here to help you find the perfect job! Tell me about yourself.</p>
        <button onClick={handleResetConversation} className={styles.resetButton}>
          Reset Conversation
        </button>
      </header>

      {error && <div className={styles.errorMessage}>{error}</div>}

      <section className={styles.chatbotMessages}>
        {messages.map((message) => (
          <div
            key={message.id}
            className={`${styles.message} ${message.sender === "user" ? styles.userMessage : styles.botMessage}`}
          >
            <div className={styles.messageContent}>{message.text}</div>
            <div className={styles.messageTime}>
              {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className={`${styles.message} ${styles.botMessage}`}>
            <div className={styles.typingIndicator}>
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </section>

      {candidateInfo && Object.values(candidateInfo).some(v => v) && (
        <section className={styles.candidateInfo}>
          <h3>Your Information</h3>
          <div className={styles.infoGrid}>
            {candidateInfo.name && (
              <div className={styles.infoItem}>
                <strong>Name:</strong> {candidateInfo.name}
              </div>
            )}
            {candidateInfo.location && (
              <div className={styles.infoItem}>
                <strong>Location:</strong> {candidateInfo.location}
              </div>
            )}
            {candidateInfo.looking_for && (
              <div className={styles.infoItem}>
                <strong>Looking for:</strong> {candidateInfo.looking_for}
              </div>
            )}
            {candidateInfo.skills && (
              <div className={styles.infoItem}>
                <strong>Skills:</strong> {candidateInfo.skills}
              </div>
            )}
            {candidateInfo.availability && (
              <div className={styles.infoItem}>
                <strong>Availability:</strong> {candidateInfo.availability}
              </div>
            )}
          </div>
        </section>
      )}

      <form onSubmit={handleSubmit} className={styles.chatbotInputForm}>
        <div className={styles.inputContainer}>
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type your message here..."
            disabled={isLoading}
            className={styles.chatbotInput}
          />
          <button
            type="button"
            onClick={handleVoiceRecord}
            disabled={isLoading}
            className={`${styles.voiceButton} ${isRecording ? styles.recording : ""}`}
            aria-label={isRecording ? "Stop recording" : "Start recording"}
          >
            {isRecording ? "⏹️" : "🎤"}
          </button>
          <button
            type="submit"
            disabled={isLoading || !inputText.trim()}
            className={styles.sendButton}
          >
            Send
          </button>
        </div>
      </form>
    </main>
  );
}
