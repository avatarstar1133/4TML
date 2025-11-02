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
    
    // Khai báo các phần tử mới
    const downloadOutputBtn = document.getElementById('downloadOutputBtn');
    const processingStatusArea = document.getElementById('processingStatusArea');
    // Kết thúc khai báo

    const chatInputContainer = document.querySelector('.chat-input-container');
    const fileSendButton = document.createElement('button');
    fileSendButton.className = 'button-small file-send-button';
    fileSendButton.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
            <path d="M19.5 5.25l-7.5 7.5-7.5-7.5m15 6l-7.5 7.5-7.5-7.5" />
        </svg>
    `;
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
        downloadOutputBtn.style.display = 'none'; // Ẩn nút tải file
        processingStatusArea.textContent = ''; // Xóa trạng thái
    });
    
    // *** CẬP NHẬT: Xử lý nút Tải file với kiểm tra file tồn tại ***
    downloadOutputBtn.addEventListener('click', async () => {
        try {
            // Kiểm tra trạng thái xử lý trước
            const statusResponse = await fetch('http://127.0.0.1:5000/api/check_status');
            const statusData = await statusResponse.json();
            
            // Nếu đang xử lý, hiển thị thông báo
            if (statusData.status === 'processing') {
                alert('⏳ Vui lòng chờ trong giây lát!\n\nHệ thống đang xử lý dữ liệu của bạn. File output.txt sẽ sẵn sàng sau khi hoàn tất.');
                return;
            }
            
            // Nếu xử lý thất bại
            if (statusData.status === 'failed') {
                alert('❌ Xử lý thất bại!\n\nKhông thể tạo file output.txt. Vui lòng thử lại.');
                return;
            }
            
            // Kiểm tra file có tồn tại không bằng cách thử tải
            const checkResponse = await fetch('http://127.0.0.1:5000/api/get_output');
            const checkData = await checkResponse.json();
            
            if (!checkData.success) {
                alert('⏳ Vui lòng chờ trong giây lát!\n\nFile output.txt chưa được tạo ra. Hệ thống đang xử lý dữ liệu của bạn.');
                return;
            }
            
            // Nếu file tồn tại, tiến hành tải xuống
            processingStatusArea.textContent = '📥 Đang tải file output.txt...';
            window.location.href = 'http://127.0.0.1:5000/api/download_output';
            
            // Sau 1 giây, cập nhật trạng thái
            setTimeout(() => {
                processingStatusArea.textContent = '✅ Đã tải xuống thành công!';
            }, 1000);
            
        } catch (error) {
            console.error('Lỗi khi kiểm tra file:', error);
            alert('⚠️ Lỗi kết nối!\n\nKhông thể kết nối đến server. Vui lòng kiểm tra lại.');
        }
    });


    function handleFileSelection(e) {
        const file = e.target.files[0];
        if (!file) return;

        if (file.size > 5 * 1024 * 1024) {
            alert('File quá lớn. Vui lòng chọn file dưới 5MB.');
            return;
        }

        const reader = new FileReader();
        reader.onload = (event) => {
            const base64Data = event.target.result.split(',')[1];
            
            // 1. Hiển thị tin nhắn người dùng
            createMessageElement(`Đang tải tệp: ${file.name} (${(file.size / 1024).toFixed(2)} KB)...`, 'user');
            
            // 2. Kích hoạt luồng chờ
            startProcessingFlow(null, base64Data);
        };
        reader.readAsDataURL(file);
    }
    
    // HÀM CHÍNH XỬ LÝ LUỒNG CHỜ VÀ GỌI API (ĐÃ CHỈNH SỬA)
    function startProcessingFlow(userPrompt, fileDataBase64 = null) {
        
        // Ẩn nút tải file và xóa trạng thái khi bắt đầu xử lý
        downloadOutputBtn.style.display = 'none';
        processingStatusArea.textContent = '⏳ Chuẩn bị dữ liệu...';

        // 1. Hiển thị thông báo chờ ngay lập tức
        const initialResponseElement = createMessageElement("⏳ Đang gửi yêu cầu... Vui lòng chờ kết quả từ AI Agent...", 'ai');
        
        // 2. Hiển thị hiệu ứng typing indicator (chờ thêm)
        const typingIndicator = showTypingIndicator(); 
        
        let processingDone = false;
        
        // Hàm kiểm tra trạng thái từ backend sau mỗi 2 giây
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
            
        }, 2000); // Kiểm tra mỗi 2 giây
        
        // 3. Thiết lập độ trễ 5 giây (giả định thời gian xử lý)
        setTimeout(async () => {
            
            // Đánh dấu luồng xử lý chính kết thúc
            processingDone = true;
            clearInterval(checkStatusInterval); // Dừng việc kiểm tra trạng thái sau khi hết 5s

            // Loại bỏ thông báo chờ và typing indicator
            if (initialResponseElement.parentElement) {
                chatWindow.removeChild(initialResponseElement);
            }
            if (typingIndicator.parentElement) {
                chatWindow.removeChild(typingIndicator);
            }
            
            // 4. GỌI API để lấy kết quả thực tế
            await simulateAIResponse(userPrompt, fileDataBase64);
            
            // Cập nhật trạng thái cuối cùng và hiển thị nút tải file
            const statusResponse = await fetch('http://127.0.0.1:5000/api/check_status');
            const statusData = await statusResponse.json();

            if (statusData.status === 'completed') {
                downloadOutputBtn.style.display = 'flex'; // Hiện nút tải file
                processingStatusArea.innerHTML = `✅ **Xử lý hoàn tất** - ${new Date(statusData.timestamp).toLocaleTimeString()}`;
            } else if (statusData.status === 'failed') {
                processingStatusArea.innerHTML = `❌ **Xử lý thất bại** - ${new Date(statusData.timestamp).toLocaleTimeString()}`;
            }
            
        }, 5000); // 5000ms = 5 giây (Thời gian chờ mô phỏng)
    }


    async function simulateAIResponse(userPrompt, fileDataBase64 = null) {
        
        try {
            const payload = {
                prompt: userPrompt,
                file_data: fileDataBase64
                // Giữ nguyên use_agent = false, app.py sẽ tự mô phỏng agent
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
            
            // Hiển thị phản hồi từ BE
            createMessageElement(data.ai_response_text, 'ai');
            
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

        // BẮT ĐẦU LUỒNG CHỜ
        startProcessingFlow(messageText); 
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