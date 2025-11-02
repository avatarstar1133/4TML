document.addEventListener('DOMContentLoaded', () => {

    const themeToggleButton = document.getElementById('theme-toggle-button');
    const body = document.body;
    const themeLogo = document.getElementById('theme-logo'); 

    const LOGO_DARK = 'pict/logo_dark.png';
    const LOGO_LIGHT = 'pict/logo_light.png';
    
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.txt,.pdf,.docx';
    fileInput.style.display = 'none';
    document.body.appendChild(fileInput);

    function applyTheme(isDark) {
        if (isDark) {
            body.classList.add('dark-theme');
            themeToggleButton.textContent = '☀️';
            localStorage.setItem('theme', 'dark-theme');
            if (themeLogo) themeLogo.src = LOGO_DARK; 
        } else {
            body.classList.remove('dark-theme');
            themeToggleButton.textContent = '🌙';
            localStorage.setItem('theme', 'light-theme');
            if (themeLogo) themeLogo.src = LOGO_LIGHT;
        }
    }

    const savedTheme = localStorage.getItem('theme');
    const isDarkTheme = savedTheme ? savedTheme === 'dark-theme' : true; 
    applyTheme(isDarkTheme);

    themeToggleButton.addEventListener('click', () => {
        const isCurrentlyDark = body.classList.contains('dark-theme');
        applyTheme(!isCurrentlyDark);
    });

    const chatWindow = document.getElementById('chatWindow');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const newChatBtn = document.getElementById('newChatBtn');
    const welcomeMessage = document.getElementById('welcomeMessage');
    
    const downloadOutputBtn = document.getElementById('downloadOutputBtn');
    const processingStatusArea = document.getElementById('processingStatusArea');

    const chatInputContainer = document.querySelector('.chat-input-container');
    const fileSendButton = document.createElement('button');
    fileSendButton.className = 'button-small file-send-button';
    fileSendButton.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
            <path fill-rule="evenodd" d="M18.97 3.659a2.25 2.25 0 00-3.182 0l-10.94 10.94a3.75 3.75 0 105.304 5.303l7.693-7.693a.75.75 0 011.06 1.06l-7.693 7.693a5.25 5.25 0 11-7.424-7.424l10.939-10.94a3.75 3.75 0 115.303 5.304L9.097 18.835l-.008.008-.007.007-.002.002-.003.002A2.25 2.25 0 015.91 15.66l7.81-7.81a.75.75 0 011.061 1.06l-7.81 7.81a.75.75 0 001.054 1.068L18.97 6.84a2.25 2.25 0 000-3.182z" clip-rule="evenodd" />
        </svg>
    `;
    fileSendButton.title = "Tải file lên";
    chatInputContainer.insertBefore(fileSendButton, chatInput);
    
    fileSendButton.addEventListener('click', () => {
        fileInput.click();
    });
    
    fileInput.addEventListener('change', handleFileSelection);

    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    newChatBtn.addEventListener('click', () => {
        chatWindow.innerHTML = '';
        chatWindow.appendChild(welcomeMessage);
        welcomeMessage.style.display = 'flex';
        chatInput.value = '';
        scrollToBottom();
        downloadOutputBtn.style.display = 'none';
        processingStatusArea.textContent = '';
    });
    
    downloadOutputBtn.addEventListener('click', async () => {
        try {
            const statusResponse = await fetch('http://127.0.0.1:5000/api/check_status');
            const statusData = await statusResponse.json();
            
            if (statusData.status === 'processing') {
                alert('⏳ Vui lòng chờ trong giây lát!\n\nHệ thống đang xử lý dữ liệu của bạn. File output.txt sẽ sẵn sàng sau khi hoàn tất.');
                return;
            }
            
            if (statusData.status === 'failed') {
                alert('❌ Xử lý thất bại!\n\nKhông thể tạo file output.txt. Vui lòng thử lại.');
                return;
            }
            
            const checkResponse = await fetch('http://127.0.0.1:5000/api/get_output');
            const checkData = await checkResponse.json();
            
            if (!checkData.success) {
                alert('⏳ Vui lòng chờ trong giây lát!\n\nFile output.txt chưa được tạo ra. Hệ thống đang xử lý dữ liệu của bạn.');
                return;
            }
            
            processingStatusArea.textContent = '📥 Đang tải file output.txt...';
            window.location.href = 'http://127.0.0.1:5000/api/download_output';
            
            setTimeout(() => {
                processingStatusArea.textContent = '✅ Đã tải xuống thành công!';
                setTimeout(() => {
                    processingStatusArea.textContent = '';
                }, 3000);
            }, 1000);
            
        } catch (error) {
            console.error('Lỗi khi kiểm tra file:', error);
            alert('⚠️ Lỗi kết nối!\n\nKhông thể kết nối đến server. Vui lòng kiểm tra lại.');
        }
    });

    function handleFileSelection(e) {
        const file = e.target.files[0];
        if (!file) return;

        const allowedExtensions = ['.txt', '.pdf', '.docx'];
        const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        
        if (!allowedExtensions.includes(fileExtension)) {
            alert('❌ Định dạng file không hợp lệ!\n\nVui lòng chọn file .txt, .pdf hoặc .docx');
            fileInput.value = '';
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            alert('📦 File quá lớn!\n\nVui lòng chọn file dưới 5MB.');
            fileInput.value = '';
            return;
        }

        const reader = new FileReader();
        reader.onload = (event) => {
            const base64Data = event.target.result.split(',')[1];
            createMessageElement(`📎 Đang tải tệp: ${file.name} (${(file.size / 1024).toFixed(2)} KB)...`, 'user');
            startProcessingFlow(null, base64Data);
        };
        
        reader.onerror = () => {
            alert('❌ Lỗi đọc file!\n\nKhông thể đọc file. Vui lòng thử lại.');
            fileInput.value = '';
        };
        
        reader.readAsDataURL(file);
        fileInput.value = '';
    }
    
    function startProcessingFlow(userPrompt, fileDataBase64 = null) {
        downloadOutputBtn.style.display = 'none';
        processingStatusArea.textContent = '⏳ Chuẩn bị dữ liệu...';

        const initialResponseElement = createMessageElement("⏳ Đang gửi yêu cầu... Vui lòng chờ kết quả từ AI Agent...", 'ai');
        const typingIndicator = showTypingIndicator(); 
        
        let processingDone = false;
        
        const checkStatusInterval = setInterval(async () => {
            if (processingDone) {
                clearInterval(checkStatusInterval);
                return;
            }
            
            try {
                 const statusResponse = await fetch('http://127.0.0.1:5000/api/check_status');
                 const statusData = await statusResponse.json();
                 
                 if (statusData.status === 'completed') {
                     processingStatusArea.innerHTML = `✅ **Xử lý hoàn tất** - ${new Date(statusData.timestamp).toLocaleTimeString()}`;
                 } else if (statusData.status === 'failed') {
                     processingStatusArea.innerHTML = `❌ **Xử lý thất bại** - ${new Date(statusData.timestamp).toLocaleTimeString()}`;
                 } else if (statusData.status === 'processing') {
                     processingStatusArea.innerHTML = `⏳ **Agent đang xử lý**... (${new Date().toLocaleTimeString()})`;
                 } else {
                     processingStatusArea.innerHTML = `🌐 **Sẵn sàng**`;
                 }
            } catch (error) {
                 processingStatusArea.innerHTML = `⚠️ **Lỗi kết nối Backend**`;
            }
            
        }, 2000);
        
        setTimeout(async () => {
            processingDone = true;
            clearInterval(checkStatusInterval);

            if (initialResponseElement.parentElement) {
                chatWindow.removeChild(initialResponseElement);
            }
            if (typingIndicator.parentElement) {
                chatWindow.removeChild(typingIndicator);
            }
            
            await simulateAIResponse(userPrompt, fileDataBase64);
            
            const statusResponse = await fetch('http://127.0.0.1:5000/api/check_status');
            const statusData = await statusResponse.json();

            if (statusData.status === 'completed') {
                downloadOutputBtn.style.display = 'flex';
                processingStatusArea.innerHTML = `✅ **Xử lý hoàn tất** - ${new Date(statusData.timestamp).toLocaleTimeString()}`;
            } else if (statusData.status === 'failed') {
                processingStatusArea.innerHTML = `❌ **Xử lý thất bại** - ${new Date(statusData.timestamp).toLocaleTimeString()}`;
            }
            
        }, 5000);
    }

    async function simulateAIResponse(userPrompt, fileDataBase64 = null) {
        try {
            const payload = {
                prompt: userPrompt,
                file_data: fileDataBase64
            };
            
            const response = await fetch('http://127.0.0.1:5000/api/process_prompt', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            // Hiển thị phản hồi với format markdown
            createFormattedMessage(data.ai_response_text, 'ai');
            
        } catch (error) {
            console.error("Lỗi khi gọi Backend:", error);
            createMessageElement("❌ Lỗi: Không thể kết nối hoặc xử lý dữ liệu từ Backend.", 'ai');
        }
    }

    function sendMessage() {
        const messageText = chatInput.value.trim();
        if (messageText === '') return;

        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }

        createMessageElement(messageText, 'user');
        chatInput.value = '';
        autoResizeTextarea(chatInput);

        startProcessingFlow(messageText); 
    }
    
    // HÀM MỚI: Tạo message với format markdown đẹp
    function createFormattedMessage(text, sender) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', sender, 'formatted-message');
        
        // Parse markdown-style text thành HTML
        const formattedHTML = parseMarkdownToHTML(text);
        messageElement.innerHTML = formattedHTML;
        
        chatWindow.appendChild(messageElement);
        scrollToBottom();
        return messageElement;
    }
    
    // HÀM MỚI: Parse markdown đơn giản thành HTML
    function parseMarkdownToHTML(text) {
        let html = text;
        
        // Headers (# ## ###)
        html = html.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>');
        
        // Bold (**text** or __text__)
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
        
        // Italic (*text* or _text_)
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/_(.+?)_/g, '<em>$1</em>');
        
        // Bullet points
        html = html.replace(/^\* (.+)$/gm, '<li class="md-li">$1</li>');
        html = html.replace(/^- (.+)$/gm, '<li class="md-li">$1</li>');
        
        // Wrap consecutive <li> in <ul>
        html = html.replace(/(<li class="md-li">.*?<\/li>\n?)+/gs, '<ul class="md-ul">$&</ul>');
        
        // Code blocks (```...```)
        html = html.replace(/```([\s\S]*?)```/g, '<pre class="md-code-block"><code>$1</code></pre>');
        
        // Inline code (`code`)
        html = html.replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>');
        
        // Line breaks
        html = html.replace(/\n\n/g, '<br><br>');
        html = html.replace(/\n/g, '<br>');
        
        return html;
    }
    
    function createMessageElement(text, sender) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', sender);
        messageElement.textContent = text;
        chatWindow.appendChild(messageElement);
        scrollToBottom();
        return messageElement;
    }

    function showTypingIndicator() {
        const typingElement = document.createElement('div');
        typingElement.classList.add('message', 'ai', 'typing');
        typingElement.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;
        chatWindow.appendChild(typingElement);
        scrollToBottom();
        return typingElement;
    }

    function scrollToBottom() {
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    chatInput.addEventListener('input', () => {
        autoResizeTextarea(chatInput);
    });

    function autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = (textarea.scrollHeight) + 'px';
    }
});