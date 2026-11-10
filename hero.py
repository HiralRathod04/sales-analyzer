import streamlit.components.v1 as components

HERO_HTML = """
<style>
  html, body { margin: 0; background: transparent; font-family: 'Segoe UI', Arial, sans-serif; }
  .wrap {
    position: relative; height: 380px; border-radius: 24px; overflow: hidden;
    background: radial-gradient(circle at 72% 40%, #2A2470 0%, #0F1433 55%, #080B1C 100%);
    border: 1px solid rgba(255,255,255,0.14);
  }
  canvas { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
  .text { position: absolute; left: 44px; top: 50%; transform: translateY(-50%);
          z-index: 2; max-width: 46%; }
  .badge { display: inline-block; padding: 6px 14px; border-radius: 999px;
           background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
           color: #cfd6ff; font-size: 12px; letter-spacing: 0.08em; margin-bottom: 16px; }
  h1 { margin: 0 0 12px 0; font-size: 42px; line-height: 1.1; color: #fff;
       text-shadow: 0 4px 24px rgba(0,0,0,0.4); }
  h1 span { background: linear-gradient(90deg, #8FD3FF, #B49CFF);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  p { margin: 0; color: #b8c0e0; font-size: 16px; line-height: 1.5; }
  @media (max-width: 700px) {
    .text { max-width: 88%; left: 24px; }
    h1 { font-size: 28px; }
    p { font-size: 14px; }
  }
</style>

<div class="wrap" id="wrap">
  <canvas id="c"></canvas>
  <div class="text">
    <div class="badge">DATA ANALYTICS TOOL</div>
    <h1>E-Commerce <span>Sales Analyzer</span></h1>
    <p>Upload any sales file. Get clean data, customer segments and a sales forecast in seconds.</p>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
  const wrap = document.getElementById('wrap');
  const canvas = document.getElementById('c');
  const renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
  camera.position.set(0, 6, 15);
  camera.lookAt(0, 1, 0);

  scene.add(new THREE.AmbientLight(0xffffff, 0.55));
  const light1 = new THREE.PointLight(0x7C5CFF, 1.8, 60); light1.position.set(6, 8, 6); scene.add(light1);
  const light2 = new THREE.PointLight(0x00D5FF, 1.5, 60); light2.position.set(-6, 4, 8); scene.add(light2);

  const group = new THREE.Group();
  scene.add(group);

  // a grid of 3D bars that rise and fall like a live bar chart
  const N = 7;
  const bars = [];
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      const geo = new THREE.BoxGeometry(0.6, 1, 0.6);
      geo.translate(0, 0.5, 0);
      const hue = 0.75 - 0.25 * (i + j) / (2 * N - 2);
      const mat = new THREE.MeshStandardMaterial({
        color: new THREE.Color().setHSL(hue, 0.8, 0.55), metalness: 0.3, roughness: 0.35
      });
      const bar = new THREE.Mesh(geo, mat);
      bar.position.set((i - (N - 1) / 2) * 0.85, 0, (j - (N - 1) / 2) * 0.85);
      bar.userData = { phase: Math.random() * 6.28 + (i + j) * 0.5 };
      group.add(bar);
      bars.push(bar);
    }
  }

  // a glowing ring around the bars
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(4.6, 0.03, 16, 120),
    new THREE.MeshBasicMaterial({ color: 0x8FD3FF })
  );
  ring.rotation.x = Math.PI / 2;
  ring.position.y = 0.05;
  group.add(ring);

  // floating particles
  const pts = [];
  for (let k = 0; k < 160; k++) {
    pts.push((Math.random() - 0.5) * 16, Math.random() * 8, (Math.random() - 0.5) * 16);
  }
  const pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  const particles = new THREE.Points(pGeo, new THREE.PointsMaterial({ color: 0xcfd6ff, size: 0.05 }));
  group.add(particles);

  let mouseX = 0;
  wrap.addEventListener('mousemove', function (e) {
    const r = wrap.getBoundingClientRect();
    mouseX = (e.clientX - r.left) / r.width - 0.5;
  });

  function resize() {
    const w = wrap.clientWidth, h = wrap.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    group.position.x = w > 700 ? 3.4 : 0;
  }
  window.addEventListener('resize', resize);
  resize();

  const clock = new THREE.Clock();
  function animate() {
    const t = clock.getElapsedTime();
    bars.forEach(function (b) {
      b.scale.y = 0.5 + 2.2 * (0.5 + 0.5 * Math.sin(t * 1.1 + b.userData.phase));
    });
    group.rotation.y = t * 0.15 + mouseX * 0.8;
    group.rotation.x = 0.12;
    particles.rotation.y = -t * 0.05;
    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }
  animate();
</script>
"""

def show_hero():
    components.html(HERO_HTML, height=400)