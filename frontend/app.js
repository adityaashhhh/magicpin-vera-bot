// app.js
// Vera 2.0 Landing Page Interactive Features
// Written for the magicpin AI Challenge

const API_BASE = window.location.port === '8080' || window.location.href.includes(':8080')
    ? ''
    : 'http://127.0.0.1:8080';

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Lucide Icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // 2. Backend health polling
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    
    async function checkHealth() {
        try {
            const start = performance.now();
            const res = await fetch(`${API_BASE}/v1/healthz`);
            const latency = Math.round(performance.now() - start);
            
            if (res.ok) {
                if (statusDot) statusDot.className = 'status-dot online';
                if (statusText) statusText.textContent = `System Live (${latency}ms)`;
            } else {
                throw new Error('Not OK');
            }
        } catch (err) {
            if (statusDot) statusDot.className = 'status-dot offline';
            if (statusText) statusText.textContent = 'System Offline';
        }
    }
    
    checkHealth();
    setInterval(checkHealth, 8000);

    // 3. Scroll-triggered reveal animations
    const revealElements = document.querySelectorAll('.reveal');
    const revealObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                el.classList.add('revealed');
                
                // Handle staggered children
                const staggerChildren = el.querySelectorAll('[data-stagger]');
                staggerChildren.forEach((child, index) => {
                    child.style.transitionDelay = `${index * 100}ms`;
                    child.classList.add('revealed');
                });
                
                observer.unobserve(el);
            }
        });
    }, { threshold: 0.15, rootMargin: '0px 0px -50px 0px' });

    revealElements.forEach(el => revealObserver.observe(el));

    // 4. Animated number counters
    const easeOutQuart = (t) => 1 - Math.pow(1 - t, 4);
    
    const counterElements = document.querySelectorAll('.counter');
    const counterObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const target = parseFloat(el.getAttribute('data-target')) || 0;
                const duration = 2000;
                let startTimestamp = null;
                
                const step = (timestamp) => {
                    if (!startTimestamp) startTimestamp = timestamp;
                    const progress = Math.min((timestamp - startTimestamp) / duration, 1);
                    const currentVal = easeOutQuart(progress) * target;
                    
                    // Format based on suffixes/prefixes in the original text or a data attribute
                    const prefix = el.getAttribute('data-prefix') || '';
                    const suffix = el.getAttribute('data-suffix') || '';
                    
                    // Simple formatting
                    let displayVal = currentVal;
                    if (target % 1 !== 0) displayVal = currentVal.toFixed(1);
                    else displayVal = Math.round(currentVal);
                    
                    el.textContent = `${prefix}${displayVal}${suffix}`;
                    
                    if (progress < 1) {
                        window.requestAnimationFrame(step);
                    }
                };
                
                window.requestAnimationFrame(step);
                observer.unobserve(el);
            }
        });
    }, { threshold: 0.1 });
    
    counterElements.forEach(el => counterObserver.observe(el));

    // 5. Smooth scroll for nav links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetEl = document.querySelector(targetId);
            if (targetEl) {
                const headerOffset = 80; // Adjust for sticky header
                const elementPosition = targetEl.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.scrollY - headerOffset;
                
                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });

    // 6. Header scroll effect
    const header = document.querySelector('header');
    if (header) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                header.classList.add('scrolled');
            } else {
                header.classList.remove('scrolled');
            }
        });
    }

    // 7. Three.js particle system
    initThreeJsParticles();

    // 8. Spline 3D hero
    initHeroSplineScene();

    // 9. Live Simulator
    const runSimBtn = document.getElementById('run-sim-btn');
    if (runSimBtn) {
        runSimBtn.addEventListener('click', async () => {
            const triggerEl = document.getElementById('sim-trigger');
            const trigger = triggerEl ? triggerEl.value : '';
            
            // UI Loading state
            const originalText = runSimBtn.innerHTML;
            runSimBtn.innerHTML = '<span class="loader"></span> Executing...';
            runSimBtn.disabled = true;
            
            try {
                const start = performance.now();
                const res = await fetch(`${API_BASE}/v1/tick`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ trigger })
                });
                const data = await res.json();
                const latency = Math.round(performance.now() - start);
                
                // Update UI
                updateSimUI(data, latency);
                showToast('Execution completed successfully', 'success');
            } catch (err) {
                console.error(err);
                showToast('Execution failed. Check console.', 'error');
            } finally {
                runSimBtn.innerHTML = originalText;
                runSimBtn.disabled = false;
            }
        });
    }

    function updateSimUI(data, latency) {
        const setEl = (id, html) => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = html;
        };
        
        // Typing animation for body preview
        const bodyPreview = document.getElementById('out-body-preview');
        if (bodyPreview) {
            bodyPreview.innerHTML = '';
            typeWriter(bodyPreview, data.body || 'No message generated', 30);
        }
        
        setEl('out-rationale-text', data.rationale || 'N/A');
        setEl('out-send-as', data.send_as || 'N/A');
        setEl('out-supp-key', data.supp_key || 'N/A');
        setEl('out-raw-json', JSON.stringify(data, null, 2));
        setEl('exec-latency', `${latency}ms`);
        
        const ctaEl = document.getElementById('exec-cta');
        if (ctaEl) {
            ctaEl.textContent = data.send_as === 'whatsapp' ? 'Simulate WhatsApp' : 'View Action';
        }
    }

    function typeWriter(element, text, speed) {
        let i = 0;
        element.innerHTML = '';
        function type() {
            if (i < text.length) {
                element.innerHTML += text.charAt(i);
                i++;
                setTimeout(type, speed);
            }
        }
        type();
    }

    // 10. Multi-turn Reply Simulator
    const sendReplyBtn = document.getElementById('send-reply-btn');
    const replyInput = document.getElementById('sim-reply-input');
    
    if (sendReplyBtn && replyInput) {
        sendReplyBtn.addEventListener('click', async () => {
            const text = replyInput.value.trim();
            const merchantEl = document.getElementById('sim-merchant');
            const merchantId = merchantEl ? merchantEl.value : 'default';
            
            if (!text) return;
            
            const originalText = sendReplyBtn.innerHTML;
            sendReplyBtn.innerHTML = '<span class="loader-sm"></span> Sending...';
            sendReplyBtn.disabled = true;
            
            try {
                const res = await fetch(`${API_BASE}/v1/reply`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, merchant_id: merchantId })
                });
                const data = await res.json();
                
                // Show result in toast or UI
                showToast('Reply processed', 'success');
                replyInput.value = '';
                
                // If there's a response message, show it
                if (data.response) {
                    setTimeout(() => showToast(`Vera: ${data.response}`, 'info'), 1000);
                }
            } catch (err) {
                showToast('Failed to send reply', 'error');
            } finally {
                sendReplyBtn.innerHTML = originalText;
                sendReplyBtn.disabled = false;
            }
        });
        
        // 16. Keyboard shortcuts for reply
        replyInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendReplyBtn.click();
            }
        });
    }

    // 12. WhatsApp Auto-Play Demo
    initWhatsAppDemo();

    // 13. Score dimension visualizer
    const scoreBars = document.querySelectorAll('.score-bar');
    const scoreObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const score = parseFloat(el.getAttribute('data-score')) || 0;
                const width = Math.min((score / 10) * 100, 100);
                
                setTimeout(() => {
                    el.style.width = `${width}%`;
                }, 200);
                
                observer.unobserve(el);
            }
        });
    }, { threshold: 0.2 });
    
    scoreBars.forEach(bar => scoreObserver.observe(bar));

    // 14. Parallax effect
    window.addEventListener('scroll', () => {
        const scrolled = window.scrollY;
        const parallaxElements = document.querySelectorAll('.parallax');
        
        parallaxElements.forEach(el => {
            const speed = el.getAttribute('data-speed') || 0.5;
            el.style.transform = `translateY(${scrolled * speed}px)`;
        });
    });

    // 15. Category tab switcher
    const tabButtons = document.querySelectorAll('#category-tabs .tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active from all
            tabButtons.forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.category-panel').forEach(p => {
                p.classList.remove('active');
                p.style.opacity = 0;
                p.style.display = 'none';
            });
            
            // Add active to clicked
            btn.classList.add('active');
            const category = btn.getAttribute('data-category');
            const panel = document.querySelector(`.category-panel[data-category="${category}"]`);
            
            if (panel) {
                panel.classList.add('active');
                panel.style.display = 'block';
                setTimeout(() => {
                    panel.style.opacity = 1;
                }, 50);
            }
        });
    });

    // 16. Keyboard shortcuts (Escape)
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Close any modals
            document.querySelectorAll('.modal.active').forEach(modal => {
                modal.classList.remove('active');
            });
        }
    });

});

// 11. Global function to set reply text
window.setSimReply = function(text) {
    const input = document.getElementById('sim-reply-input');
    if (input) {
        input.value = text;
        input.focus();
    }
};

// 17. Toast notifications
window.showToast = function(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:10px;';
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const colors = {
        success: '#10b981',
        error: '#ef4444',
        info: '#3b82f6',
        warning: '#f59e0b'
    };
    
    toast.style.cssText = `
        background: #1e293b;
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        border-left: 4px solid ${colors[type] || colors.info};
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        font-family: system-ui, -apple-system, sans-serif;
        transform: translateX(120%);
        transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    `;
    
    toast.textContent = message;
    container.appendChild(toast);
    
    // Animate in
    requestAnimationFrame(() => {
        toast.style.transform = 'translateX(0)';
    });
    
    // Animate out and remove
    setTimeout(() => {
        toast.style.transform = 'translateX(120%)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
};

// --- Three.js Implementation ---
function initThreeJsParticles() {
    const container = document.getElementById('spine-canvas-container');
    const canvas = document.getElementById('hero-3d-canvas');
    if (!container || !canvas || typeof THREE === 'undefined') return;

    const scene = new THREE.Scene();
    
    const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.z = 100;

    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const particlesCount = 350;
    const positions = new Float32Array(particlesCount * 3);
    const colors = new Float32Array(particlesCount * 3);
    
    // Brand colors: green (#00ff88), cyan (#00d2ff), purple (#8b5cf6)
    const colorPalette = [
        new THREE.Color(0x00ff88),
        new THREE.Color(0x00d2ff),
        new THREE.Color(0x8b5cf6)
    ];

    for (let i = 0; i < particlesCount; i++) {
        // Sphere distribution
        const theta = Math.random() * 2 * Math.PI;
        const phi = Math.acos((Math.random() * 2) - 1);
        const radius = 40 + Math.random() * 20;

        positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
        positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
        positions[i * 3 + 2] = radius * Math.cos(phi);

        const color = colorPalette[Math.floor(Math.random() * colorPalette.length)];
        colors[i * 3] = color.r;
        colors[i * 3 + 1] = color.g;
        colors[i * 3 + 2] = color.b;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    // Custom shader material for soft round particles
    const material = new THREE.PointsMaterial({
        size: 2.5,
        vertexColors: true,
        blending: THREE.AdditiveBlending,
        transparent: true,
        opacity: 0.8,
        sizeAttenuation: true
    });

    const particles = new THREE.Points(geometry, material);
    scene.add(particles);

    // Lines connecting nearby particles
    const lineMaterial = new THREE.LineBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.15,
        blending: THREE.AdditiveBlending
    });
    
    const lineGeometry = new THREE.BufferGeometry();
    const lineMesh = new THREE.LineSegments(lineGeometry, lineMaterial);
    scene.add(lineMesh);

    // Mouse interaction
    const mouse = new THREE.Vector2(0, 0);
    const targetMouse = new THREE.Vector2(0, 0);
    const raycaster = new THREE.Raycaster();
    const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
    const mouseV3 = new THREE.Vector3();

    window.addEventListener('mousemove', (e) => {
        const rect = renderer.domElement.getBoundingClientRect();
        targetMouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        targetMouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    });

    const originalPositions = positions.slice();

    // Animation loop
    const clock = new THREE.Clock();

    function animate() {
        requestAnimationFrame(animate);
        
        const time = clock.getElapsedTime();
        
        // Smooth mouse movement
        mouse.x += (targetMouse.x - mouse.x) * 0.05;
        mouse.y += (targetMouse.y - mouse.y) * 0.05;

        // Slow rotation
        particles.rotation.y = time * 0.05;
        particles.rotation.x = time * 0.02;
        lineMesh.rotation.y = time * 0.05;
        lineMesh.rotation.x = time * 0.02;

        const currentPositions = particles.geometry.attributes.position.array;
        const linePositions = [];
        
        // Setup raycaster for mouse repulsion
        raycaster.setFromCamera(mouse, camera);
        raycaster.ray.intersectPlane(plane, mouseV3);
        
        for (let i = 0; i < particlesCount; i++) {
            const idx = i * 3;
            
            const origX = originalPositions[idx];
            const origY = originalPositions[idx+1];
            const origZ = originalPositions[idx+2];
            
            // Waving animation
            const waveX = origX + Math.sin(time + origY * 0.1) * 1.5;
            const waveY = origY + Math.cos(time + origX * 0.1) * 1.5;
            const waveZ = origZ;
            
            // Mouse repulsion in local space (approximate)
            // Just repel outwards if close to center
            const dx = waveX - (mouse.x * 50);
            const dy = waveY - (mouse.y * 50);
            const dist = Math.sqrt(dx*dx + dy*dy);
            
            let finalX = waveX;
            let finalY = waveY;
            
            if (dist < 20) {
                const force = (20 - dist) / 20;
                finalX += (dx / dist) * force * 5;
                finalY += (dy / dist) * force * 5;
            }
            
            currentPositions[idx] = finalX;
            currentPositions[idx+1] = finalY;
            currentPositions[idx+2] = waveZ;
            
            // Check distances for lines
            for (let j = i + 1; j < particlesCount; j++) {
                const jdx = j * 3;
                const dX = currentPositions[idx] - currentPositions[jdx];
                const dY = currentPositions[idx+1] - currentPositions[jdx+1];
                const dZ = currentPositions[idx+2] - currentPositions[jdx+2];
                const distSq = dX*dX + dY*dY + dZ*dZ;
                
                if (distSq < 900) { // distance < 30
                    linePositions.push(
                        currentPositions[idx], currentPositions[idx+1], currentPositions[idx+2],
                        currentPositions[jdx], currentPositions[jdx+1], currentPositions[jdx+2]
                    );
                }
            }
        }
        
        particles.geometry.attributes.position.needsUpdate = true;
        lineMesh.geometry.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));

        renderer.render(scene, camera);
    }

    animate();

    // Resize handler
    window.addEventListener('resize', () => {
        if (!container) return;
        const width = container.clientWidth;
        const height = container.clientHeight;
        
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        
        renderer.setSize(width, height);
    });
}

// --- Spline 3D Hero ---
async function initHeroSplineScene() {
    const canvas = document.getElementById('spline-hero-canvas');
    if (!canvas) return;

    try {
        const { Application } = await import('https://esm.sh/@splinetool/runtime');
        const app = new Application(canvas);
        app.load('https://prod.spline.design/a0jskNJyOg-9FkYo/scene.splinecode');
    } catch (err) {
        console.error('Failed to load Spline scene:', err);
    }
}

// --- WhatsApp Auto-Play Demo ---
function initWhatsAppDemo() {
    const container = document.getElementById('wa-demo-container');
    if (!container) return;
    
    const messages = [
        { type: 'incoming', text: 'Hi, I saw your post about dental scaling. What is the cost?', delay: 1000 },
        { type: 'typing', delay: 1500 },
        { type: 'outgoing', text: 'Hi! Welcome to Dr. Meera\\'s Dental Clinic! 🦷 We currently have a special offer for dental scaling at just ₹999 (usually ₹1500). Would you like to book an appointment?', delay: 3000 },
        { type: 'incoming', text: 'Yes, tomorrow evening at 5 PM?', delay: 6000 },
        { type: 'typing', delay: 1500 },
        { type: 'outgoing', text: 'Perfect! I have booked your appointment for tomorrow at 5:00 PM for dental scaling. See you soon! ✨', delay: 4000 }
    ];
    
    function runSequence() {
        container.innerHTML = '';
        let currentTime = 0;
        
        messages.forEach(msg => {
            currentTime += msg.delay;
            
            setTimeout(() => {
                if (msg.type === 'typing') {
                    const typingEl = document.createElement('div');
                    typingEl.className = 'wa-bubble wa-bubble-outgoing typing-indicator';
                    typingEl.id = 'wa-typing';
                    typingEl.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
                    container.appendChild(typingEl);
                    container.scrollTop = container.scrollHeight;
                } else {
                    const typingEl = document.getElementById('wa-typing');
                    if (typingEl) typingEl.remove();
                    
                    const msgEl = document.createElement('div');
                    msgEl.className = \`wa-bubble wa-bubble-\${msg.type}\`;
                    msgEl.style.animation = 'fadeInUp 0.3s ease forwards';
                    msgEl.textContent = msg.text;
                    container.appendChild(msgEl);
                    container.scrollTop = container.scrollHeight;
                }
            }, currentTime);
        });
        
        // Loop every 15 seconds after finish
        setTimeout(runSequence, currentTime + 5000);
    }
    
    // Add CSS for the demo if not present
    if (!document.getElementById('wa-demo-styles')) {
        const style = document.createElement('style');
        style.id = 'wa-demo-styles';
        style.textContent = \`
            .wa-bubble {
                padding: 10px 14px;
                border-radius: 12px;
                margin-bottom: 8px;
                max-width: 80%;
                font-size: 14px;
                line-height: 1.4;
                opacity: 0;
                transform: translateY(10px);
                position: relative;
            }
            .wa-bubble-incoming {
                background: #2a3942;
                color: #e9edef;
                align-self: flex-start;
                border-top-left-radius: 0;
            }
            .wa-bubble-outgoing {
                background: #005c4b;
                color: #e9edef;
                align-self: flex-end;
                border-top-right-radius: 0;
                margin-left: auto;
            }
            .typing-indicator {
                display: flex;
                gap: 4px;
                padding: 14px 16px;
                align-items: center;
                width: fit-content;
            }
            .typing-indicator .dot {
                width: 6px;
                height: 6px;
                background: #aebac1;
                border-radius: 50%;
                animation: typingBounce 1s infinite;
            }
            .typing-indicator .dot:nth-child(2) { animation-delay: 0.2s; }
            .typing-indicator .dot:nth-child(3) { animation-delay: 0.4s; }
            
            @keyframes typingBounce {
                0%, 100% { transform: translateY(0); }
                50% { transform: translateY(-4px); }
            }
            @keyframes fadeInUp {
                to { opacity: 1; transform: translateY(0); }
            }
        \`;
        document.head.appendChild(style);
    }
    
    // Start sequence
    runSequence();
}
