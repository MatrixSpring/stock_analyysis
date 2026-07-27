/** 动画性能优化：页面隐藏时暂停所有动画，减少卡顿掉帧 */
export function initTechAnimationControl() {
  document.addEventListener('visibilitychange', () => {
    const state = document.hidden ? 'paused' : 'running';
    document.querySelectorAll('.breath-light,.scan-line,.dsa-card-active,.cyber-pulse,.ai-stream-text')
      .forEach((el: any) => { el.style.animationPlayState = state; });
  });
}
