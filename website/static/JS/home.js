document.addEventListener("DOMContentLoaded", () => {
  // ── Particle System Setup ──
  const canvas = document.getElementById("festiveParticles");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  let particles = [];
  let isGarbaMode = false;

  // Resize canvas to match the parent container
  function resizeCanvas() {
    const parent = canvas.parentElement;
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight;
  }
  resizeCanvas();
  window.addEventListener("resize", resizeCanvas);

  // Particle Class Definition (Highly Optimized, NO shadowBlur to prevent CPU lag)
  class FestiveParticle {
    constructor(isBurst = false, burstX = 0, burstY = 0) {
      this.isBurst = isBurst;
      this.x = isBurst ? burstX : Math.random() * canvas.width;
      this.type = Math.random() > 0.45 ? "spark" : "petal"; 
      this.y = isBurst 
        ? burstY 
        : (this.type === "spark" ? canvas.height + Math.random() * 30 : -Math.random() * 30);
      
      this.size = this.type === "spark" ? Math.random() * 2 + 1 : Math.random() * 5 + 4;
      
      // Speed vectors
      if (isBurst) {
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 3 + 1;
        this.vx = Math.cos(angle) * speed;
        this.vy = Math.sin(angle) * speed;
      } else {
        this.vx = (Math.random() - 0.5) * 0.5;
        this.vy = this.type === "spark" ? -(Math.random() * 0.8 + 0.4) : (Math.random() * 0.7 + 0.5);
      }

      // Slate & Gold Theme Cohesive Colors
      if (this.type === "spark") {
        const goldHues = ["#fef08a", "#fef08a", "#d4af37", "#f59e0b"]; // Slate-gold friendly tones
        this.color = goldHues[Math.floor(Math.random() * goldHues.length)];
      } else {
        const goldColors = ["#d4af37", "#b8961e", "#f59e0b", "#fbbf24"]; 
        this.color = goldColors[Math.floor(Math.random() * goldColors.length)];
      }

      this.alpha = Math.random() * 0.4 + 0.5;
      this.decay = isBurst ? 0.025 : 0.0025;
      
      // Petal spin attributes
      this.angle = Math.random() * Math.PI;
      this.spin = (Math.random() - 0.5) * 0.03;
      this.sway = Math.random() * 100;
      this.swaySpeed = Math.random() * 0.015 + 0.005;
    }

    update() {
      if (this.isBurst) {
        this.x += this.vx;
        this.y += this.vy;
        this.vy += 0.03; // gravity
      } else {
        this.x += this.vx;
        this.y += this.vy;
        if (this.type === "petal") {
          this.x += Math.sin(this.sway) * 0.25;
          this.sway += this.swaySpeed;
          this.angle += this.spin;
        }
      }
      this.alpha -= this.decay;
    }

    draw() {
      ctx.save();
      ctx.globalAlpha = this.alpha;
      ctx.fillStyle = this.color;
      
      if (this.type === "spark") {
        // Simple circle spark (NO shadowBlur is critical for 60 FPS performance)
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fill();
      } else {
        // Simpler lightweight petal diamond path (extremely fast to draw)
        ctx.translate(this.x, this.y);
        ctx.rotate(this.angle);
        ctx.beginPath();
        ctx.moveTo(0, -this.size);
        ctx.lineTo(this.size * 0.5, 0);
        ctx.lineTo(0, this.size);
        ctx.lineTo(-this.size * 0.5, 0);
        ctx.closePath();
        ctx.fill();
      }
      ctx.restore();
    }
  }

  // Animation Loop
  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Low, highly optimized particle cap
    const maxParticles = isGarbaMode ? 60 : 30;
    if (particles.length < maxParticles && Math.random() < 0.15) {
      particles.push(new FestiveParticle());
    }

    // Update & draw particles
    particles = particles.filter(p => {
      p.update();
      p.draw();
      return p.alpha > 0 && p.x >= 0 && p.x <= canvas.width && p.y >= -50 && p.y <= canvas.height + 50;
    });

    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);

  // ── Interactive Mood / Garba Mode Toggle ──
  const moodBtn = document.getElementById("garbaMoodToggle");
  const pageContainer = document.getElementById("festiveHomepage");

  if (moodBtn && pageContainer) {
    moodBtn.addEventListener("click", () => {
      isGarbaMode = !isGarbaMode;
      pageContainer.classList.toggle("garba-mode", isGarbaMode);

      const toggleText = moodBtn.querySelector(".toggle-text");
      if (isGarbaMode) {
        toggleText.textContent = "Night Garba Mode Active!";
        moodBtn.style.borderColor = "var(--theme-gold)";
        playCelebrationChime();
      } else {
        toggleText.textContent = "Toggle Festive Garba Lights";
        moodBtn.style.borderColor = "rgba(212, 175, 55, 0.25)";
      }

      // Generate burst of gold sparkles from the button coordinates
      const rect = moodBtn.getBoundingClientRect();
      const parentRect = canvas.parentElement.getBoundingClientRect();
      const x = rect.left - parentRect.left + rect.width / 2;
      const y = rect.top - parentRect.top + rect.height / 2;
      
      for (let i = 0; i < 20; i++) { // optimized burst count
        particles.push(new FestiveParticle(true, x, y));
      }
    });
  }

  // ── Synthetic Audio Effects (Web Audio API) ──
  function playSoundTone(frequency = 750, duration = 0.08, type = "sine") {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(frequency, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(100, audioCtx.currentTime + duration);

      gainNode.gain.setValueAtTime(0.12, audioCtx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);

      osc.connect(gainNode);
      gainNode.connect(audioCtx.destination);

      osc.start();
      osc.stop(audioCtx.currentTime + duration);
    } catch (err) {
      // AudioContext blocks until interaction
    }
  }

  function playCelebrationChime() {
    try {
      const notes = [440, 554.37, 659.25, 880]; // A4, C#5, E5, A5 chords
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      
      notes.forEach((freq, index) => {
        const time = audioCtx.currentTime + index * 0.08;
        const osc = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();

        osc.type = "sine";
        osc.frequency.setValueAtTime(freq, time);

        gainNode.gain.setValueAtTime(0.08, time);
        gainNode.gain.exponentialRampToValueAtTime(0.001, time + 0.25);

        osc.connect(gainNode);
        gainNode.connect(audioCtx.destination);

        osc.start(time);
        osc.stop(time + 0.3);
      });
    } catch (err) {
      // Ignore block
    }
  }

  // ── Interactive Hover Sounds for Category Cards ──
  const categoryCards = document.querySelectorAll(".traditional-category-card");
  categoryCards.forEach(card => {
    let hoverTimeout = null;

    card.addEventListener("mouseenter", () => {
      hoverTimeout = setTimeout(() => {
        // Play a premium soft magic bell/sparkle chime on card hover
        playSoundTone(960, 0.12, "sine");
        
        // Spawn sparks in the center of the mirror frame
        const frame = card.querySelector(".card-mirror-frame");
        if (frame) {
          const rect = frame.getBoundingClientRect();
          const parentRect = canvas.parentElement.getBoundingClientRect();
          const cx = rect.left - parentRect.left + rect.width / 2;
          const cy = rect.top - parentRect.top + rect.height / 2;
          for (let k = 0; k < 6; k++) {
            particles.push(new FestiveParticle(true, cx, cy));
          }
        }
      }, 250);
    });

    card.addEventListener("mouseleave", () => {
      if (hoverTimeout) {
        clearTimeout(hoverTimeout);
      }
    });
  });
});
