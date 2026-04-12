import React, { useEffect, useRef } from 'react';

// === 核心数据：3D 原生轨道专属加密徽标矩阵 ===
const CRYPTO_LOGOS = [
    '/crypto/btc.svg',
    '/crypto/eth.svg',
    '/crypto/solana.svg',
    '/crypto/bnb.svg',
    '/crypto/usdt.svg',
    '/crypto/usdc.svg',
    '/crypto/xrp.svg'
];

export default function InteractiveBackground({ children }) {
    const canvasRef = useRef(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d', { alpha: false });
        let animationFrameId;

        // 1. 本地图片静态缓冲
        const loadedIcons = new Array(CRYPTO_LOGOS.length).fill(null);
        CRYPTO_LOGOS.forEach((src, i) => {
            const img = new Image();
            img.src = src;
            img.onload = () => { loadedIcons[i] = img; };
        });

        // 2. 3D 全息投影数学引擎配置
        const cfg = {
            fLen: 1200,             // 摄像机焦距视角 (Focal Length)
            sphereRadius: 650,      // 矩阵全息球的物理包络大小
            particleCount: 700,     // 悬浮点的数量，构建高密度骨架构架
            logoOrbitMultiplier: 1.35, // Crypto Logo 的赤道轨道距乘数
            bgColor: '#060809'
        };

        const spheres = [];
        const logos = [];
        let mouseX = 0, mouseY = 0;
        let targetRotX = 0, targetRotY = 0;
        let rotX = 0, rotY = 0;

        let cx = 0, cy = 0;

        // ==========================
        // 初始化原生物理三维点系
        // ==========================
        const init3DUniverse = () => {
            spheres.length = 0;
            logos.length = 0;

            const dpr = window.devicePixelRatio || 1;
            const w = window.innerWidth;
            const h = window.innerHeight;
            cx = w / 2;
            cy = h / 2;

            // 采用 Fibonacci Sphere (黄金螺旋) 算法生成极其均匀漂亮的三维球壳点阵
            const phi = Math.PI * (3 - Math.sqrt(5));
            for (let i = 0; i < cfg.particleCount; i++) {
                // 将y从 -1 映射到 1
                const y = 1 - (i / (cfg.particleCount - 1)) * 2;
                const rad = Math.sqrt(1 - y * y);
                const theta = phi * i;

                const x = Math.cos(theta) * rad;
                const z = Math.sin(theta) * rad;

                // 每一个点带有基于中心的原生绝对 3D 坐标
                spheres.push({
                    ox: x * cfg.sphereRadius,
                    oy: y * cfg.sphereRadius,
                    oz: z * cfg.sphereRadius,
                    // 给点一些呼吸极化值
                    baseSize: 1 + Math.random() * 2,
                    phase: Math.random() * Math.PI * 2
                });
            }

            // 初始化 3D 赤道倾斜环轨道上的加密 Logo 实体
            for (let i = 0; i < CRYPTO_LOGOS.length; i++) {
                // 存储轨位角度而不是写死的绝对坐标，以赋予生命期的独立公转能力
                const angle = (Math.PI * 2 / CRYPTO_LOGOS.length) * i;
                const orbitR = Math.max(800, cfg.sphereRadius * cfg.logoOrbitMultiplier);
                // 形成一个立体的空间八字环线的高度插值
                const py = Math.sin(angle * 2) * 200;

                // BNB, BTC 随机赋予不同的大小基数
                const baseS = (CRYPTO_LOGOS[i].includes('btc')) ? 180 :
                    (CRYPTO_LOGOS[i].includes('eth') || CRYPTO_LOGOS[i].includes('sol')) ? 140 : 100;

                logos.push({
                    baseAngle: angle,
                    orbitR: orbitR,
                    yPosition: py,
                    speedRatio: 0.7 + Math.random() * 0.6, // 微妙的公转速度随机差分
                    iconIndex: i,
                    baseSize: baseS,
                });
            }
        };

        const resize = () => {
            const dpr = window.devicePixelRatio || 1;
            canvas.width = window.innerWidth * dpr;
            canvas.height = window.innerHeight * dpr;
            ctx.scale(dpr, dpr);
            init3DUniverse();
        };
        window.addEventListener('resize', resize);
        resize();

        // 将鼠标的桌面 XY 位置截获并转化为 3D 相机的 X/Y 欧拉旋转角目标
        const handleMouseMove = (e) => {
            // 针对视口中央的值：从 -1 ~ 1
            const nx = (e.clientX - window.innerWidth / 2) / (window.innerWidth / 2);
            const ny = (e.clientY - window.innerHeight / 2) / (window.innerHeight / 2);
            targetRotY = nx * 1.5;
            targetRotX = -ny * 1.5;
        };
        const handleMouseLeave = () => {
            targetRotX = 0; targetRotY = 0;
        };

        let btnFocus = { active: false, x: 0, y: 0, w: 0, h: 0, cx: 0, cy: 0 };
        const handleFocusBtn = (e) => { btnFocus = e.detail; };

        window.addEventListener('mousemove', handleMouseMove, { passive: true });
        document.addEventListener('mouseleave', handleMouseLeave);
        window.addEventListener('FOCUS_BTN_AREA', handleFocusBtn);

        let time = 0;

        const draw = () => {
            time += 16;
            const w = window.innerWidth;
            const h = window.innerHeight;

            // 底图不再完全擦除而产生带有极化虚影的黑场以模拟极高空间动态感
            ctx.fillStyle = 'rgba(6, 8, 9, 0.45)';
            ctx.fillRect(0, 0, w, h);

            // 发光点阵透镜氛围层
            const radGrad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, 800);
            radGrad.addColorStop(0, 'rgba(16, 185, 129, 0.08)');
            radGrad.addColorStop(1, 'transparent');
            ctx.fillStyle = radGrad;
            ctx.fillRect(0, 0, w, h);

            // =====================================
            // 3D 视角相机矩阵欧拉解算推演器
            // =====================================
            // 逼近鼠标引发的目标旋转量，结合放大过后的时间自传，让骨架有直观的漂移感
            rotX += (targetRotX - rotX) * 0.05 + 0.0006;
            rotY += (targetRotY - rotY) * 0.05 + 0.0035;

            const cosX = Math.cos(rotX), sinX = Math.sin(rotX);
            const cosY = Math.cos(rotY), sinY = Math.sin(rotY);

            // Z-Buffer: 打破先来后到，由于 3D 物体互相重叠，必须算好远近交错
            const renderQueue = [];

            // 预解算并投射核心网格系
            for (let i = 0; i < spheres.length; i++) {
                const p = spheres[i];
                // 让骨架发生一点原生的心跳涨缩起伏
                const distRate = 1 + Math.sin(time * 0.002 + p.phase) * 0.03;
                let ox = p.ox * distRate;
                let oy = p.oy * distRate;
                let oz = p.oz * distRate;

                // 绕 Y 轴偏转矩阵
                let x1 = ox * cosY - oz * sinY;
                let z1 = oz * cosY + ox * sinY;

                // 绕 X 轴偏转矩阵
                let y2 = oy * cosX - z1 * sinX;
                let z2 = z1 * cosX + oy * sinX;

                // 3D 摄像机投影，获得真实近大远小
                const perspective = cfg.fLen / (cfg.fLen + z2);
                let projX = cx + x1 * perspective;
                let projY = cy + y2 * perspective;

                // 记录下如果没有 DOM 引力干扰下的天体最原始投射座标
                const originProjX = projX;
                const originProjY = projY;

                // ==========================================
                // 跨界物理桥梁：粒子探测到特定 DOM 信号发生矩形向心引力重组
                // ==========================================
                let isBorderMark = false;
                let suctionForce = 0; // 记录拖拽拉引力的大小用于渲染速度残影

                if (btnFocus.active) {
                    let dcbx = projX - btnFocus.cx;
                    let dcby = projY - btnFocus.cy;
                    let distToBtn = Math.sqrt(dcbx * dcbx + dcby * dcby);

                    // 扩大捕抓阈值到 900PX！让全场超过一半的星空都能感受到坍缩拉扯
                    if (distToBtn < 900) {
                        let targetEdgeX = projX;
                        let targetEdgeY = projY;

                        // DOM 按钮边界稍微放缩一点
                        const hw = btnFocus.w / 2 + 4;
                        const hh = btnFocus.h / 2 + 4;

                        // 计算它会被扯到哪四个边框的附着点
                        if (Math.abs(dcbx / hw) > Math.abs(dcby / hh)) {
                            targetEdgeX = dcbx > 0 ? btnFocus.cx + hw : btnFocus.cx - hw;
                            targetEdgeY = btnFocus.cy + dcby;
                        } else {
                            targetEdgeY = dcby > 0 ? btnFocus.cy + hh : btnFocus.cy - hh;
                            targetEdgeX = btnFocus.cx + dcbx;
                        }

                        // 修改引力曲线，引入流光滞阻感 (距离在900内开始发生微拉扯，但在300内突然失控)
                        suctionForce = Math.pow(Math.max(0, 1 - (distToBtn / 900)), 2.5);
                        projX += (targetEdgeX - projX) * suctionForce;
                        projY += (targetEdgeY - projY) * suctionForce;

                        // 若它已被拉到终点附近，则认定它归属于高强发光的外边框
                        if (suctionForce > 0.4) {
                            isBorderMark = true;
                        }
                    }
                }

                renderQueue.push({
                    type: 'point',
                    x: projX, y: projY, z: z2,
                    originX: originProjX, originY: originProjY,
                    suction: suctionForce,
                    scale: perspective,
                    size: p.baseSize,
                    phase: p.phase,
                    isBorder: isBorderMark
                });
            }

            // 预解算 SVG 卫星轨道实体
            for (let i = 0; i < logos.length; i++) {
                const lg = logos[i];

                // 让图形拥有自身沿着赤道高速独立自转滑行的专属公转解算！
                const selfAngle = lg.baseAngle + time * 0.00035 * lg.speedRatio;
                let lX = Math.cos(selfAngle) * lg.orbitR;
                let lZ = Math.sin(selfAngle) * lg.orbitR;
                let lY = lg.yPosition;

                // 然后再带着自身的位移受限于全局矩阵宇宙一起产生 3D 转子偏转投射
                let x1 = lX * cosY - lZ * sinY;
                let z1 = lZ * cosY + lX * sinY;

                let y2 = lY * cosX - z1 * sinX;
                let z2 = z1 * cosX + lY * sinX;

                const perspective = cfg.fLen / (cfg.fLen + z2);
                const projX = cx + x1 * perspective;
                const projY = cy + y2 * perspective;

                renderQueue.push({
                    type: 'logo',
                    x: projX, y: projY, z: z2,
                    scale: perspective,
                    baseSize: lg.baseSize,
                    img: loadedIcons[lg.iconIndex]
                });
            }

            // 最硬核环节：Z-Index 引擎缓冲排序法，Z轴越深（数值越正且越大，意味着摄像机越远），则越早绘制让前面覆盖
            renderQueue.sort((a, b) => b.z - a.z);

            // =====================================
            // 按深度 Z 轴透视递进并渲染呈现
            // =====================================
            for (let item of renderQueue) {
                if (item.type === 'point') {
                    // 1. 如果它正在经历拉扯冲刺：绘制出极高能的拖尾光痕轨迹
                    if (item.suction > 0.05 && !item.isBorder) {
                        ctx.beginPath();
                        ctx.moveTo(item.originX, item.originY);
                        ctx.lineTo(item.x, item.y);
                        // 利用吸附力度推算发光绿色尾焰强度，形成汇流瀑布
                        ctx.strokeStyle = `rgba(16, 185, 129, ${Math.min(0.8, item.suction * 2)})`;
                        ctx.lineWidth = Math.max(0.5, item.scale * 1.5);
                        ctx.stroke();
                    }

                    // 2. 绘制星体原生粒子点本身
                    ctx.beginPath();
                    ctx.arc(item.x, item.y, Math.max(0.2, item.size * item.scale), 0, Math.PI * 2);

                    if (item.isBorder) {
                        // 对已经形成真实边框的稳态核心光子剥离深度规则，重着色为结晶形态
                        ctx.shadowBlur = 15;
                        ctx.shadowColor = '#10b981'; // 荧光祖母绿
                        const spark = 0.6 + Math.sin(time * 0.005 + item.phase) * 0.4;
                        ctx.fillStyle = `rgba(255, 255, 255, ${spark})`;
                        ctx.fill();
                        ctx.shadowBlur = 0;
                    } else if (item.suction > 0.05) {
                        // 如果是在受力飞行途中的离子体，让它极亮化变成炽热白心
                        ctx.fillStyle = `rgba(255, 255, 255, ${Math.min(1, item.suction * 3)})`;
                        ctx.fill();
                    } else {
                        // 普通深空未受波及的点，正常随距离暗淡
                        const intensity = item.scale;
                        const rA = Math.min(1, Math.max(0.05, intensity * 1.5 - 0.5));
                        const lumaBase = intensity * 255;

                        ctx.fillStyle = `rgba(${lumaBase * 0.8}, ${lumaBase}, ${lumaBase}, ${rA + Math.cos(time * 0.002 + item.phase) * 0.15})`;
                        ctx.fill();
                    }
                }
                else if (item.type === 'logo') {
                    if (!item.img) continue; // 图片未下载完则等候

                    const drawSize = item.baseSize * item.scale;
                    if (drawSize <= 0) continue;

                    ctx.save();
                    // 当这个星星转到球的最前方(Z为极端的负)，其 scale 比如大于 1.2，产生惊悚且绝美的 3D 悬空遮挡光晕
                    if (item.scale > 1.0) {
                        ctx.shadowBlur = 40 * (item.scale - 1);
                        ctx.shadowColor = 'rgba(255, 255, 255, 0.4)';
                    } else {
                        ctx.shadowBlur = 0;
                    }
                    // 背面的图形也会发生绝对的三维遮蔽暗化
                    const imgAlpha = Math.min(1, Math.max(0.15, item.scale * 1.5 - 0.3));
                    ctx.globalAlpha = imgAlpha;

                    ctx.drawImage(item.img, item.x - drawSize / 2, item.y - drawSize / 2, drawSize, drawSize);
                    ctx.restore();
                }
            }

            animationFrameId = requestAnimationFrame(draw);
        };

        draw();

        return () => {
            window.removeEventListener('resize', resize);
            window.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseleave', handleMouseLeave);
            window.removeEventListener('FOCUS_BTN_AREA', handleFocusBtn);
            cancelAnimationFrame(animationFrameId);
        };
    }, []);

    return (
        <div className="pointer-events-none fixed inset-0 z-0 h-full w-full overflow-hidden bg-[#060809]">
            {/* 独有的量化极客重头戏：3D Projection 点阵骨架全景世界 */}
            <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} className="block w-full h-full" />
            <div className="absolute inset-0 z-10 w-full h-full pointer-events-auto">
                {children}
            </div>
        </div>
    );
}
