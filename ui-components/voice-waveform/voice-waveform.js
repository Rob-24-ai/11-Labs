const canvas = document.getElementById('waveform');
const ctx = canvas.getContext('2d');
const btn = document.getElementById('toggle-btn');

let audioCtx = null;
let analyser = null;
let dataArray = null;
let source = null;
let stream = null;
let running = false;
let isBeeping = false;
let beepStartTime = 0;
let beepDuration = 800; // Duration of beep in milliseconds

function getAmplitude(data) {
  // Compute normalized amplitude (0..1)
  let sum = 0;
  for (let i = 0; i < data.length; i++) {
    let v = data[i] - 128;
    sum += v * v;
  }
  return Math.sqrt(sum / data.length) / 128;
}

function draw() {
  if (!running) return;
  requestAnimationFrame(draw);
  analyser.getByteTimeDomainData(dataArray);
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Always get user mic amplitude
  const avgMicAmplitude = dataArray.reduce((sum, val) => sum + Math.abs(val - 128), 0) / dataArray.length;
  const micAmplitude = Math.min(1, Math.max(0, avgMicAmplitude / 50)); // Normalize mic amplitude 0-1

  // Default state - respond to microphone input
  let activeAmplitude = micAmplitude;
  let scale = 1; // Default scale (no change)
  
  if (isBeeping) {
    // Check if beep is still active
    const elapsedTime = Date.now() - beepStartTime;
    if (elapsedTime < beepDuration) {
      // Calculate beep amplitude - start soft and ramp up then fade out
      const progress = elapsedTime / beepDuration;
      let beepAmplitude;
      if (progress < 0.2) {
        beepAmplitude = 0.8 * progress / 0.2; // Ramp up
      } else {
        beepAmplitude = 0.8 * (1 - (progress - 0.2) / 0.8); // Fade out
      }
      
      // Use beep amplitude and expand the ring
      activeAmplitude = beepAmplitude;
      scale = 1 + beepAmplitude * 0.05; // Further reduced expansion factor (was 0.08)
    } else {
      // Beep finished
      isBeeping = false;
    }
  } else if (activeAmplitude > 0.05) {
    // Only contract if actual user voice is detected (above threshold)
    scale = 1 - activeAmplitude * 0.15; // Shrink for user speaking
  }

  // --- Dynamic Offset Calculation ---
  // Use a larger base offset and more dramatic scaling for better visibility
  const baseOffset = 5; // Increased base offset for more dramatic effect
  let dynamicOffset;
  
  // Use a more subtle shadow shift that's proportional to the scale change
  dynamicOffset = baseOffset * scale;
  
  // --- Dynamic Alpha Calculation for Beep --- 
  let shadowAlpha = 0.7;
  let glowAlpha = 0.9;
  if (isBeeping) {
    // Increase alpha slightly based on beep amplitude to make edges sharper when expanded
    shadowAlpha = 0.7 + activeAmplitude * 0.3; // Increased multiplier (was 0.2), Max 0.94
    glowAlpha = 0.9 + activeAmplitude * 0.125; // Increased multiplier (was 0.1) to reach 1.0 at peak
    
    // --- New non-linear shadow intensification ---
    const progress = (Date.now() - beepStartTime) / beepDuration;
    const maxShadowAlpha = 1.0; // Target max darkness (increased from 0.95)
    const baseShadowAlpha = 0.7;
    const shadowRange = maxShadowAlpha - baseShadowAlpha; // Now 0.3

    if (progress < 0.2) {
        // Ramp up phase (quadratic increase for faster intensification near peak)
        const rampProgress = progress / 0.2;
        shadowAlpha = baseShadowAlpha + Math.pow(rampProgress, 2) * shadowRange;
    } else if (progress < 1.0) {
        // Fade out phase (linear decrease back to base)
        const fadeProgress = (progress - 0.2) / 0.8;
        shadowAlpha = maxShadowAlpha - fadeProgress * shadowRange;
    } else {
       shadowAlpha = baseShadowAlpha; // Ensure it resets after beep
    }
    // --- ------------------------------------- ---
  }
  // --- ---------------------------------- ---

  const baseRadius = 45; // Smaller radius
  const ringWidth = 12; // Reverted back from 15
  const cx = canvas.width / 2;
  const cy = canvas.height / 2 + 20;

  // First pass: bottom-right shadow (darker)
  ctx.save();
  ctx.shadowColor = `rgba(143, 157, 178, ${Math.min(1, shadowAlpha)})`; // Ensure alpha doesn't exceed 1.0
  ctx.shadowBlur = 8 + activeAmplitude * 8; // Use activeAmplitude for pulsing
  ctx.shadowOffsetX = dynamicOffset; // Dynamic offset X
  ctx.shadowOffsetY = dynamicOffset; // Dynamic offset Y
  ctx.beginPath();
  ctx.arc(cx, cy, baseRadius * scale, 0, Math.PI * 2, false);
  ctx.arc(cx, cy, (baseRadius - ringWidth) * scale, 0, Math.PI * 2, true);
  ctx.closePath();
  ctx.fillStyle = '#E0E5EC'; // Updated fill color
  ctx.fill();
  ctx.restore();
  
  // Second pass: top-left glow (lighter with subtle color) - REINSTATED TO MATCH BUTTONS
  ctx.save();
  ctx.shadowColor = `rgba(255, 255, 255, ${Math.min(1, glowAlpha)})`; // Ensure alpha doesn't exceed 1.0
  ctx.shadowBlur = 12 + activeAmplitude * 5; // Use activeAmplitude for pulsing
  ctx.shadowOffsetX = -dynamicOffset; // Dynamic offset X (negative)
  ctx.shadowOffsetY = -dynamicOffset; // Dynamic offset Y (negative)
  ctx.beginPath();
  ctx.arc(cx, cy, baseRadius * scale, 0, Math.PI * 2, false);
  ctx.arc(cx, cy, (baseRadius - ringWidth) * scale, 0, Math.PI * 2, true);
  ctx.closePath();
  ctx.fillStyle = '#E0E5EC'; // Updated fill color
  ctx.fill();
  ctx.restore(); 
  

  /* // Draw subtle outline - REMOVED TO MATCH BUTTON STYLE
  ctx.save();
  ctx.lineWidth = 2;
  ctx.strokeStyle = 'rgba(180, 190, 200, 0.3)'; // Darker, more visible outline
  ctx.beginPath();
  ctx.arc(cx, cy, baseRadius * scale, 0, Math.PI * 2);
  ctx.closePath();
  ctx.stroke();
  ctx.restore();
  */
}

async function start() {
  stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 1024;
  dataArray = new Uint8Array(analyser.fftSize);
  source = audioCtx.createMediaStreamSource(stream);
  source.connect(analyser);
  running = true;
  btn.textContent = 'Stop';
  draw();
}

function stop() {
  running = false;
  btn.textContent = 'Start';
  if (audioCtx) {
    audioCtx.close();
    audioCtx = null;
  }
  if (stream) {
    stream.getTracks().forEach(track => track.stop());
    stream = null;
  }
}

function playBeep() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  
  // Create oscillator for beep sound
  const oscillator = audioCtx.createOscillator();
  const gainNode = audioCtx.createGain();
  
  // Configure oscillator
  oscillator.type = 'sine';
  oscillator.frequency.setValueAtTime(880, audioCtx.currentTime); // A5 note
  
  // Configure gain (volume) with fade out
  gainNode.gain.setValueAtTime(0.5, audioCtx.currentTime);
  gainNode.gain.linearRampToValueAtTime(0, audioCtx.currentTime + beepDuration/1000);
  
  // Connect and start
  oscillator.connect(gainNode);
  gainNode.connect(audioCtx.destination);
  oscillator.start();
  oscillator.stop(audioCtx.currentTime + beepDuration/1000);
  
  // Set state for visual feedback
  isBeeping = true;
  beepStartTime = Date.now();
  
  console.log('Beep played');
}

btn.addEventListener('click', () => {
  if (!running) {
    start();
  } else {
    stop();
  }
});

// Add event listener for beep button
const beepBtn = document.getElementById('beep-btn');
if (beepBtn) {
  beepBtn.addEventListener('click', playBeep);
}

window.addEventListener('beforeunload', stop);
