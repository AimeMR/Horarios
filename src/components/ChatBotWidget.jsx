import React, { useState, useRef, useEffect } from 'react';
import { useLanguage } from '../context/LanguageContext';
import {
  getAiConfig,
  saveAiConfig,
  sendMessageToLocalAI,
  generateSimulatedResponse
} from '../services/aiChatService';

export default function ChatBotWidget() {
  const { lang, t } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  // Configuración de la IA Local
  const [config, setConfig] = useState(() => getAiConfig());
  const [settingsForm, setSettingsForm] = useState(() => getAiConfig());
  const [showApiKey, setShowApiKey] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState(false);

  // Historial de mensajes
  const [messages, setMessages] = useState(() => [
    {
      id: 'welcome-msg',
      sender: 'assistant',
      text: `${t('chatbot.welcomeGreeting')}\n\n${t('chatbot.welcomeDesc')}`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      isInitial: true
    }
  ]);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll al final del chat cuando se añaden mensajes o cambia el estado
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
      inputRef.current?.focus();
    }
  }, [isOpen, messages, isGenerating, isSettingsOpen]);

  // Actualiza el mensaje de bienvenida al cambiar de idioma si no hay conversación avanzada
  useEffect(() => {
    setMessages((prev) => {
      if (prev.length === 1 && prev[0].isInitial) {
        return [
          {
            id: 'welcome-msg',
            sender: 'assistant',
            text: `${t('chatbot.welcomeGreeting')}\n\n${t('chatbot.welcomeDesc')}`,
            timestamp: prev[0].timestamp,
            isInitial: true
          }
        ];
      }
      return prev;
    });
  }, [lang]);

  // Sincroniza el formulario de configuración al abrir los ajustes
  useEffect(() => {
    if (isSettingsOpen) {
      setSettingsForm(getAiConfig());
      setSaveSuccessMsg(false);
    }
  }, [isSettingsOpen]);

  const handleToggleChat = () => {
    setIsOpen((prev) => !prev);
  };

  const handleClearMessages = () => {
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        sender: 'assistant',
        text: `${t('chatbot.welcomeGreeting')}\n\n${t('chatbot.welcomeDesc')}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isInitial: true
      }
    ]);
  };

  const handleSaveSettings = (e) => {
    e.preventDefault();
    const updated = saveAiConfig(settingsForm);
    setConfig(updated);
    setSaveSuccessMsg(true);
    setTimeout(() => {
      setSaveSuccessMsg(false);
      setIsSettingsOpen(false);
    }, 1200);
  };

  const handleApplyPreset = (presetType) => {
    if (presetType === 'ollama') {
      setSettingsForm((prev) => ({
        ...prev,
        url: 'http://localhost:11434/v1/chat/completions',
        model: prev.model || 'llama3'
      }));
    } else if (presetType === 'lmstudio') {
      setSettingsForm((prev) => ({
        ...prev,
        url: 'http://localhost:1234/v1/chat/completions',
        model: prev.model || 'local-model'
      }));
    }
  };

  /**
   * Envía el mensaje del usuario y consulta inmediatamente a la IA local con la API Key.
   */
  const handleSendMessage = async (textToSend = null) => {
    const text = (textToSend !== null ? textToSend : inputValue).trim();
    if (!text || isGenerating) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsgId = `user-${Date.now()}`;
    const botMsgId = `bot-${Date.now() + 1}`;

    // 1. Mensaje del usuario añadido de forma inmediata
    const newUserMsg = {
      id: userMsgId,
      sender: 'user',
      text,
      timestamp: timeStr
    };

    // 2. Mensaje de respuesta del asistente creado inmediatamente debajo con estado cargando
    const newBotPlaceholder = {
      id: botMsgId,
      sender: 'assistant',
      text: '',
      isLoading: true,
      timestamp: timeStr,
      userPromptRef: text
    };

    const currentHistory = [...messages, newUserMsg];
    setMessages([...currentHistory, newBotPlaceholder]);
    setInputValue('');
    setIsGenerating(true);

    try {
      // 3. Petición a la IA local pasando el texto, historial, idioma y configuración (con API Key)
      const result = await sendMessageToLocalAI(text, currentHistory, { lang, config });

      if (result.success) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botMsgId
              ? {
                  ...m,
                  text: result.text || '(Respuesta vacía)',
                  isLoading: false,
                  modelUsed: result.model
                }
              : m
          )
        );
      } else {
        // En caso de que el servidor local no responda o falle la autenticación/API Key
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botMsgId
              ? {
                  ...m,
                  text: '',
                  isLoading: false,
                  isError: true,
                  errorMsg: result.error,
                  errorUrl: result.url,
                  isConnectionError: result.isConnectionError
                }
              : m
          )
        );
      }
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === botMsgId
            ? {
                ...m,
                text: '',
                isLoading: false,
                isError: true,
                errorMsg: err.message
              }
            : m
        )
      );
    } finally {
      setIsGenerating(false);
    }
  };

  /**
   * Genera una respuesta simulada de demostración si el usuario la solicita ante un error de conexión
   */
  const handleTryDemoResponse = (botMsgId, userPrompt) => {
    const simulated = generateSimulatedResponse(userPrompt, lang);
    setMessages((prev) =>
      prev.map((m) =>
        m.id === botMsgId
          ? {
              ...m,
              text: simulated,
              isLoading: false,
              isError: false,
              isSimulated: true
            }
          : m
      )
    );
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const hasApiKey = Boolean(config.apiKey && config.apiKey.trim());

  return (
    <>
      {/* ======================================================================
          1. BOTÓN FLOTANTE ABAJO A LA DERECHA (CON SÍMBOLO DE CHAT)
          ====================================================================== */}
      <button
        type="button"
        className={`chatbot-floating-trigger ${isOpen ? 'is-active' : ''}`}
        onClick={handleToggleChat}
        title={t('chatbot.floatingBtnTitle')}
        aria-label={t('chatbot.floatingBtnAria')}
        aria-expanded={isOpen}
      >
        {isOpen ? (
          // Ícono de cerrar (X) cuando la pestaña está abierta
          <svg
            className="chatbot-trigger-icon"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        ) : (
          // Símbolo de chat cuando está cerrado
          <svg
            className="chatbot-trigger-icon"
            width="26"
            height="26"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
        )}

        {/* Punto de estado online en la esquina del botón */}
        <span className="chatbot-online-dot" aria-hidden="true"></span>
      </button>

      {/* ======================================================================
          2. PESTAÑA DESPLEGABLE ESTILO CHAT
          ====================================================================== */}
      {isOpen && (
        <section
          className="chatbot-window-tab"
          role="region"
          aria-label={t('chatbot.title')}
        >
          {/* Cabecera del chat */}
          <header className="chatbot-header">
            <div className="chatbot-header-info">
              <div className="chatbot-avatar-circle">
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="3" y="11" width="18" height="10" rx="2"></rect>
                  <circle cx="12" cy="5" r="2"></circle>
                  <path d="M12 7v4"></path>
                  <line x1="8" y1="16" x2="8" y2="16"></line>
                  <line x1="16" y1="16" x2="16" y2="16"></line>
                </svg>
                <span className={`avatar-status-pill ${isGenerating ? 'is-busy' : 'is-online'}`}></span>
              </div>
              <div className="chatbot-header-text">
                <h3 className="chatbot-header-title">{t('chatbot.title')}</h3>
                <div className="chatbot-header-sub">
                  <span className="chatbot-status-label">
                    {isGenerating ? t('chatbot.statusThinking') : t('chatbot.statusOnline')}
                  </span>
                  <span className="chatbot-sub-sep">•</span>
                  <span
                    className={`chatbot-api-badge ${hasApiKey ? 'is-active' : 'is-missing'}`}
                    onClick={() => setIsSettingsOpen(true)}
                    title={hasApiKey ? t('chatbot.apiKeyActive') : t('chatbot.apiKeyMissing')}
                  >
                    {hasApiKey ? '🔑 Key OK' : '⚠️ Sin Key'}
                  </span>
                </div>
              </div>
            </div>

            {/* Botones de acción en la cabecera */}
            <div className="chatbot-header-actions">
              <button
                type="button"
                className={`chatbot-icon-btn ${isSettingsOpen ? 'is-active' : ''}`}
                onClick={() => setIsSettingsOpen((prev) => !prev)}
                title={t('chatbot.settingsBtn')}
                aria-label={t('chatbot.settingsBtn')}
              >
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="3"></circle>
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                </svg>
              </button>

              <button
                type="button"
                className="chatbot-icon-btn"
                onClick={handleClearMessages}
                title={t('chatbot.clearBtn')}
                aria-label={t('chatbot.clearBtn')}
              >
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
              </button>

              <button
                type="button"
                className="chatbot-icon-btn chatbot-close-btn"
                onClick={handleToggleChat}
                title={t('chatbot.closeBtn')}
                aria-label={t('chatbot.closeBtn')}
              >
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>
          </header>

          {/* Panel Desplegable de Ajustes de IA Local (API Key, Endpoint y Modelo) */}
          {isSettingsOpen && (
            <div className="chatbot-settings-panel">
              <div className="settings-panel-header">
                <h4>{t('chatbot.settingsTitle')}</h4>
                <button
                  type="button"
                  className="settings-cancel-x"
                  onClick={() => setIsSettingsOpen(false)}
                  aria-label={t('chatbot.cancelSettings')}
                >
                  ✕
                </button>
              </div>

              <p className="settings-panel-desc">{t('chatbot.settingsDesc')}</p>

              <form onSubmit={handleSaveSettings} className="settings-form">
                {/* 1. API KEY */}
                <div className="settings-form-group">
                  <label htmlFor="settings-api-key" className="settings-label">
                    {t('chatbot.apiKeyLabel')}
                  </label>
                  <div className="settings-input-with-action">
                    <input
                      id="settings-api-key"
                      type={showApiKey ? 'text' : 'password'}
                      className="settings-input"
                      placeholder={t('chatbot.apiKeyPlaceholder')}
                      value={settingsForm.apiKey || ''}
                      onChange={(e) => setSettingsForm((prev) => ({ ...prev, apiKey: e.target.value }))}
                    />
                    <button
                      type="button"
                      className="input-peek-btn"
                      onClick={() => setShowApiKey((prev) => !prev)}
                      title={showApiKey ? 'Ocultar' : 'Mostrar'}
                    >
                      {showApiKey ? '👁️' : '🔒'}
                    </button>
                  </div>
                </div>

                {/* 2. ENDPOINT URL */}
                <div className="settings-form-group">
                  <div className="settings-label-row">
                    <label htmlFor="settings-endpoint-url" className="settings-label">
                      {t('chatbot.urlLabel')}
                    </label>
                    <div className="settings-presets">
                      <button
                        type="button"
                        className="preset-btn"
                        onClick={() => handleApplyPreset('ollama')}
                      >
                        {t('chatbot.presetOllama')}
                      </button>
                      <button
                        type="button"
                        className="preset-btn"
                        onClick={() => handleApplyPreset('lmstudio')}
                      >
                        {t('chatbot.presetLmStudio')}
                      </button>
                    </div>
                  </div>
                  <input
                    id="settings-endpoint-url"
                    type="url"
                    className="settings-input"
                    placeholder={t('chatbot.urlPlaceholder')}
                    value={settingsForm.url || ''}
                    onChange={(e) => setSettingsForm((prev) => ({ ...prev, url: e.target.value }))}
                    required
                  />
                </div>

                {/* 3. MODELO */}
                <div className="settings-form-group">
                  <label htmlFor="settings-model" className="settings-label">
                    {t('chatbot.modelLabel')}
                  </label>
                  <input
                    id="settings-model"
                    type="text"
                    className="settings-input"
                    placeholder={t('chatbot.modelPlaceholder')}
                    value={settingsForm.model || ''}
                    onChange={(e) => setSettingsForm((prev) => ({ ...prev, model: e.target.value }))}
                  />
                </div>

                {saveSuccessMsg && (
                  <div className="settings-success-alert">
                    ✓ {t('chatbot.savedSuccess')}
                  </div>
                )}

                <div className="settings-actions">
                  <button
                    type="button"
                    className="button button-secondary settings-close-btn"
                    onClick={() => setIsSettingsOpen(false)}
                  >
                    {t('chatbot.cancelSettings')}
                  </button>
                  <button type="submit" className="button button-primary settings-submit-btn">
                    {t('chatbot.saveSettings')}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* ==================================================================
              CONTENEDOR DE MENSAJES CON FORMATO CHAT
              ================================================================== */}
          <div className="chatbot-messages-scroll">
            {messages.map((msg) => {
              const isUser = msg.sender === 'user';

              return (
                <div
                  key={msg.id}
                  className={`chat-bubble-row ${isUser ? 'is-user-row' : 'is-assistant-row'}`}
                >
                  {!isUser && (
                    <div className="assistant-bubble-avatar">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                        <rect x="3" y="11" width="18" height="10" rx="2"></rect>
                        <circle cx="12" cy="5" r="2"></circle>
                        <path d="M12 7v4"></path>
                      </svg>
                    </div>
                  )}

                  <div className={`chat-bubble-card ${isUser ? 'user-card' : 'assistant-card'}`}>
                    {/* Contenido en carga: animación de 3 puntos */}
                    {msg.isLoading ? (
                      <div className="chat-typing-dots">
                        <span className="typing-dot"></span>
                        <span className="typing-dot"></span>
                        <span className="typing-dot"></span>
                        <span className="typing-text">{t('chatbot.statusThinking')}</span>
                      </div>
                    ) : msg.isError ? (
                      /* Alerta de error con acciones */
                      <div className="chat-error-box">
                        <div className="error-box-header">
                          <span className="error-icon">⚠️</span>
                          <strong>{t('chatbot.connError')}</strong>
                        </div>
                        <p className="error-box-desc">
                          {t('chatbot.connErrorDesc', msg.errorUrl || config.url)}
                        </p>
                        {msg.errorMsg && (
                          <code className="error-box-code">{msg.errorMsg}</code>
                        )}
                        <div className="error-box-actions">
                          <button
                            type="button"
                            className="error-action-btn error-action-settings"
                            onClick={() => setIsSettingsOpen(true)}
                          >
                            ⚙️ {t('chatbot.openSettingsPrompt')}
                          </button>
                          {msg.userPromptRef && (
                            <button
                              type="button"
                              className="error-action-btn error-action-demo"
                              onClick={() => handleTryDemoResponse(msg.id, msg.userPromptRef)}
                            >
                              💡 {t('chatbot.tryDemoPrompt')}
                            </button>
                          )}
                        </div>
                      </div>
                    ) : (
                      /* Mensaje de texto formateado */
                      <div className="chat-bubble-text">
                        {msg.text.split('\n\n').map((paragraph, pIdx) => (
                          <p key={pIdx}>{paragraph}</p>
                        ))}
                        {msg.isSimulated && (
                          <span className="simulated-badge">
                            [Modo Demo / Simulado]
                          </span>
                        )}
                      </div>
                    )}

                    <div className="chat-bubble-footer">
                      <span className="chat-timestamp">{msg.timestamp}</span>
                      {msg.modelUsed && (
                        <span className="chat-model-tag">{msg.modelUsed}</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Pastillas con sugerencias si solo está el mensaje de bienvenida */}
            {messages.length === 1 && !isGenerating && (
              <div className="chat-suggestion-pills">
                <button
                  type="button"
                  className="suggestion-pill"
                  onClick={() => handleSendMessage(t('chatbot.pill1'))}
                >
                  🕒 {t('chatbot.pill1')}
                </button>
                <button
                  type="button"
                  className="suggestion-pill"
                  onClick={() => handleSendMessage(t('chatbot.pill2'))}
                >
                  📍 {t('chatbot.pill2')}
                </button>
                <button
                  type="button"
                  className="suggestion-pill"
                  onClick={() => handleSendMessage(t('chatbot.pill3'))}
                >
                  ⏸️ {t('chatbot.pill3')}
                </button>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* ==================================================================
              3. ZONA DE ENTRADA DE TEXTO
              ================================================================== */}
          <footer className="chatbot-input-area">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="chatbot-input-form"
            >
              <textarea
                ref={inputRef}
                className="chatbot-textarea"
                rows="1"
                placeholder={t('chatbot.inputPlaceholder')}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isGenerating}
              />

              <button
                type="submit"
                className="chatbot-send-btn"
                disabled={!inputValue.trim() || isGenerating}
                title={t('chatbot.sendBtn')}
                aria-label={t('chatbot.sendBtn')}
              >
                {isGenerating ? (
                  <span className="send-spinner"></span>
                ) : (
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <line x1="22" y1="2" x2="11" y2="13"></line>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                  </svg>
                )}
              </button>
            </form>

            <div className="chatbot-input-note">
              <span>IA Local ({config.model || 'llama3'})</span>
              <span className="note-dot">•</span>
              <span>{hasApiKey ? 'API Key activa' : 'Pulsa ⚙️ para configurar Key'}</span>
            </div>
          </footer>
        </section>
      )}
    </>
  );
}
