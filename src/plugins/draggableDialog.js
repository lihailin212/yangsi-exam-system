import { nextTick } from 'vue'

/**
 * Global plugin that makes all el-dialog elements draggable, resizable,
 * and remembers their position/size per dialog title.
 */
export default {
  install() {
    const styleId = 'global-draggable-dialog-styles'
    if (!document.getElementById(styleId)) {
      const style = document.createElement('style')
      style.id = styleId
      style.textContent = `
        .dialog-resize-handle {
          opacity: 0.4;
          position: absolute;
          bottom: 0;
          right: 0;
          width: 20px;
          height: 20px;
          cursor: se-resize;
          z-index: 10;
          display: flex;
          align-items: center;
          justify-content: center;
          background: transparent;
          pointer-events: none;
        }
        .el-dialog:hover .dialog-resize-handle,
        .el-dialog.is-resizing .dialog-resize-handle {
          opacity: 1;
          pointer-events: auto;
        }
        .el-dialog.is-dragging { opacity: 0.9; }
        .el-dialog.is-dragging .el-dialog__header { cursor: grabbing !important; }
        .el-dialog.is-resizing * { user-select: none !important; pointer-events: none !important; }
        .el-dialog.dialog-minimized {
          /* Dialog hidden via overlay; this class is only used as a flag for state tracking */
        }
        .el-dialog.dialog-minimized:hover {
          /* no special hover needed when minimized */
        }
        .dialog-taskbar {
          position: fixed;
          bottom: 20px;
          right: 20px;
          z-index: 9999;
          display: flex;
          flex-direction: column-reverse;
          gap: 6px;
          align-items: flex-end;
        }
        .dialog-taskbar-btn {
          background: #fff;
          border: 1px solid #dcdfe6;
          border-radius: 6px;
          padding: 6px 12px;
          font-size: 12px;
          color: #303133;
          cursor: pointer !important;
          box-shadow: 0 2px 8px rgba(0,0,0,0.15);
          max-width: 180px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          display: flex;
          align-items: center;
          gap: 6px;
          user-select: none;
        }
        .dialog-taskbar-btn:hover { background: #f5f7fa; border-color: #409eff; }
        .dialog-taskbar-btn .minimize-restore-icon {
          width: 14px;
          height: 14px;
          border: 1px solid #909399;
          border-radius: 2px;
          background: #fff;
          flex-shrink: 0;
        }
        .el-dialog.dialog-maximized {
          top: 0 !important;
          left: 0 !important;
          width: 100vw !important;
          height: 100vh !important;
          border-radius: 0 !important;
          max-width: none !important;
          max-height: none !important;
          transform: none !important;
          margin: 0 !important;
        }
        .dialog-control-btns {
          display: flex !important;
          align-items: center !important;
          flex-shrink: 0 !important;
          height: 24px !important;
          gap: 8px;
          position: absolute !important;
          right: 8px !important;
          top: calc(50% - 18px) !important;
        }
        .el-dialog__header {
          display: flex !important;
          align-items: center !important;
          cursor: move !important;
          padding-right: 120px !important;
        }
        .el-dialog__headerbtn { display: none !important; }
        .dialog-control-btn {
          width: 24px !important;
          height: 24px !important;
          border: none !important;
          background: transparent !important;
          color: #909399 !important;
          cursor: pointer !important;
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          border-radius: 3px !important;
          padding: 0 !important;
          margin: 0 !important;
          transition: background-color 0.15s, color 0.15s;
          flex-shrink: 0;
          line-height: 1;
          box-sizing: border-box;
        }
        .dialog-control-btn:hover { background: #e8e8e8 !important; color: #303133 !important; }
        .dialog-control-btns .dialog-minimized-btn { margin-right: 8px !important; transform: translateY(-5px) !important; }
        .el-dialog.dialog-maximized {
          top: 0 !important;
          left: 0 !important;
          width: 100vw !important;
          height: 100vh !important;
          border-radius: 0 !important;
          max-width: none !important;
          max-height: none !important;
          transform: none !important;
          margin: 0 !important;
        }
        /* Override Element Plus max-width when restoring normal size */
        .el-dialog:not(.dialog-maximized) {
          max-width: none !important;
          max-height: none !important;
        }
      `
      document.head.appendChild(style)
    }

    const getStorageKey = (title) => `dialog_state_${title || 'default'}`
    const taskbarBtns = new Map()
    let taskbarEl = null

    const ensureTaskbar = () => {
      if (!taskbarEl) {
        taskbarEl = document.createElement('div')
        taskbarEl.className = 'dialog-taskbar'
        document.body.appendChild(taskbarEl)
      }
    }

    const addTaskbarBtn = (dialogEl, title) => {
      ensureTaskbar()
      if (taskbarBtns.has(dialogEl)) return
      const btn = document.createElement('button')
      btn.className = 'dialog-taskbar-btn'
      btn.title = title || '对话框'
      btn.innerHTML = `<span class="minimize-restore-icon"></span>${title || '对话框'}`
      btn.onclick = () => {
        const overlay = dialogEl.closest('.el-overlay')
        if (overlay) overlay.style.display = ''
        dialogEl.classList.remove('dialog-minimized')
        dialogEl.style.zIndex = ''
        btn.remove()
        taskbarBtns.delete(dialogEl)
        saveState(title, { left: parseFloat(dialogEl.style.left), top: parseFloat(dialogEl.style.top) }, { width: dialogEl.offsetWidth, height: dialogEl.offsetHeight }, false, dialogEl.classList.contains('dialog-maximized'))
      }
      taskbarEl.appendChild(btn)
      taskbarBtns.set(dialogEl, btn)
    }

    const removeTaskbarBtn = (dialogEl) => {
      const btn = taskbarBtns.get(dialogEl)
      if (btn) { btn.remove(); taskbarBtns.delete(dialogEl) }
    }

    const loadState = (title) => {
      try {
        const stored = localStorage.getItem(getStorageKey(title))
        return stored ? JSON.parse(stored) : null
      } catch { return null }
    }

    const saveState = (title, position, size, minimized, maximized) => {
      try {
        localStorage.setItem(getStorageKey(title), JSON.stringify({ position, size, minimized, maximized }))
      } catch { /* ignore */ }
    }

    // Track whether this dialog has been manually positioned (dragged/resized) by the user.
    // Only restore saved position after user has first manually moved the dialog.
    let wasManuallyPositioned = false

    const applyToDialog = (el, title) => {
      if (!el || el.dataset.draggableInitialized === 'true') return
      el.dataset.draggableInitialized = 'true'

      // Reset: each open is fresh, not restored from a prior session
      wasManuallyPositioned = false

      const header = el.querySelector('.el-dialog__header')
      if (header) {
        header.style.setProperty('position', 'relative', 'important')
      }

      if (header && !header.querySelector('.dialog-control-btns')) {
        const btnContainer = document.createElement('div')
        btnContainer.className = 'dialog-control-btns'

        const minBtn = document.createElement('button')
        minBtn.className = 'dialog-control-btn dialog-minimized-btn'
        minBtn.type = 'button'
        minBtn.title = '最小化'
        minBtn.innerHTML = `<svg width="12" height="12" viewBox="0 0 12 12"><rect x="1" y="10" width="10" height="1.5" rx="0.75" fill="currentColor"/></svg>`
        minBtn.onclick = (e) => {
          e.stopPropagation()
          const isMin = el.classList.toggle('dialog-minimized')
          const overlay = el.closest('.el-overlay')
          if (isMin) {
            // Hide the overlay so it doesn't block other page interactions
            if (overlay) overlay.style.display = 'none'
            addTaskbarBtn(el, title)
          } else {
            // Restore overlay visibility
            if (overlay) overlay.style.display = ''
            el.style.zIndex = ''
            removeTaskbarBtn(el)
          }
          const left = parseFloat(el.style.left)
          const top = parseFloat(el.style.top)
          saveState(title, { left, top }, { width: el.offsetWidth, height: el.offsetHeight }, isMin, el.classList.contains('dialog-maximized'))
        }

        const isMaximized = el.classList.contains('dialog-maximized')
        const maxBtn = document.createElement('button')
        maxBtn.className = 'dialog-control-btn dialog-maximized-btn'
        maxBtn.type = 'button'
        maxBtn.title = isMaximized ? '还原' : '最大化'
        maxBtn.innerHTML = isMaximized
          ? `<svg width="12" height="12" viewBox="0 0 12 12"><rect x="2.5" y="0.5" width="8.5" height="8.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="0.5" y="2.5" width="8.5" height="8.5" rx="1" fill="#fff" stroke="currentColor" stroke-width="1.5"/></svg>`
          : `<svg width="12" height="12" viewBox="0 0 12 12"><rect x="0.5" y="0.5" width="11" height="11" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>`
        maxBtn.onclick = (e) => {
          e.stopPropagation()
          const wasMax = el.classList.contains('dialog-maximized')
          const isMax = !wasMax
          if (isMax) {
            // Save pre-max position FIRST (before class is applied)
            const preMaxPos = { left: parseFloat(el.style.left), top: parseFloat(el.style.top) }
            const preMaxSize = { width: el.offsetWidth, height: el.offsetHeight }
            el.classList.add('dialog-maximized')
            const s = loadState(title) || {}
            saveState(title, preMaxPos, preMaxSize, s.minimized, true)
          } else {
            el.classList.remove('dialog-maximized')
            const s = loadState(title)
            if (s?.position) {
              el.style.left = `${s.position.left}px`
              el.style.top = `${s.position.top}px`
              el.style.right = 'auto'
              el.style.bottom = 'auto'
              el.style.transform = 'none'
            } else {
              el.style.left = ''
              el.style.top = ''
              el.style.right = ''
              el.style.bottom = ''
              el.style.transform = ''
            }
            if (s?.size) {
              el.style.width = `${s.size.width}px`
              el.style.height = `${s.size.height}px`
            } else {
              el.style.width = ''
              el.style.height = ''
            }
            el.style.maxWidth = ''
            el.style.maxHeight = ''
            saveState(title, s?.position, s?.size, s?.minimized, false)
          }
          maxBtn.title = isMax ? '还原' : '最大化'
          maxBtn.innerHTML = isMax
            ? `<svg width="12" height="12" viewBox="0 0 12 12"><rect x="2.5" y="0.5" width="8.5" height="8.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="0.5" y="2.5" width="8.5" height="8.5" rx="1" fill="#fff" stroke="currentColor" stroke-width="1.5"/></svg>`
            : `<svg width="12" height="12" viewBox="0 0 12 12"><rect x="0.5" y="0.5" width="11" height="11" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>`
        }

        const closeBtn = document.createElement('button')
        closeBtn.className = 'dialog-control-btn dialog-close-btn'
        closeBtn.type = 'button'
        closeBtn.title = '关闭'
        closeBtn.innerHTML = `<svg width="12" height="12" viewBox="0 0 12 12"><line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`
        closeBtn.onclick = (e) => {
          e.stopPropagation()
          // Find and click the native Element Plus close button (it handles Vue v-model correctly)
          const nativeClose = el.querySelector('.el-dialog__headerbtn')
          if (nativeClose) nativeClose.click()
        }

        btnContainer.appendChild(minBtn)
        btnContainer.appendChild(maxBtn)
        btnContainer.appendChild(closeBtn)
                header.appendChild(btnContainer)
      }

      if (!el.querySelector('.dialog-resize-handle')) {
        const rh = document.createElement('div')
        rh.className = 'dialog-resize-handle'
        rh.innerHTML = `<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><line x1="12" y1="4" x2="4" y2="12" stroke="#b0b0b0" stroke-width="1.5"/><line x1="12" y1="8" x2="8" y2="12" stroke="#b0b0b0" stroke-width="1.5"/><line x1="12" y1="12" x2="12" y2="12" stroke="#b0b0b0" stroke-width="1.5"/></svg>`
        el.appendChild(rh)
      }

      const onDragStart = (e) => {
        if (el.classList.contains('dialog-maximized')) return
        const titleBar = e.target.closest('.el-dialog__header')
        if (!titleBar) return
        if (e.target.closest('.dialog-control-btn')) return
        e.preventDefault()
        el.classList.add('is-dragging')
        // Dialog is position:fixed — getBoundingClientRect gives viewport coords naturally
        const rect = el.getBoundingClientRect()
        const offsetX = e.clientX - rect.left
        const offsetY = e.clientY - rect.top
        const onMM = (ev) => {
          el.style.left = `${ev.clientX - offsetX}px`
          el.style.top = `${ev.clientY - offsetY}px`
          el.style.right = 'auto'
          el.style.bottom = 'auto'
          el.style.transform = 'none'
        }
        const onMU = () => {
          el.classList.remove('is-dragging')
          wasManuallyPositioned = true
          // After drag, left/top are already viewport coords (fixed positioning)
          const left = parseFloat(el.style.left)
          const top = parseFloat(el.style.top)
          saveState(title, { left, top }, { width: el.offsetWidth, height: el.offsetHeight }, el.classList.contains('dialog-minimized'), el.classList.contains('dialog-maximized'))
          document.removeEventListener('mousemove', onMM)
          document.removeEventListener('mouseup', onMU)
        }
        document.addEventListener('mousemove', onMM)
        document.addEventListener('mouseup', onMU)
      }

      const onResizeStart = (e) => {
        e.preventDefault()
        e.stopPropagation()
        el.classList.add('is-resizing')
        const sx = e.clientX, sy = e.clientY, sw = el.offsetWidth, sh = el.offsetHeight
        const onMM = (ev) => {
          el.style.width = `${Math.max(300, sw + (ev.clientX - sx))}px`
          el.style.height = `${Math.max(200, sh + (ev.clientY - sy))}px`
        }
        const onMU = () => {
          el.classList.remove('is-resizing')
          wasManuallyPositioned = true
          const left = parseFloat(el.style.left)
          const top = parseFloat(el.style.top)
          saveState(title, { left, top }, { width: el.offsetWidth, height: el.offsetHeight }, el.classList.contains('dialog-minimized'), el.classList.contains('dialog-maximized'))
          document.removeEventListener('mousemove', onMM)
          document.removeEventListener('mouseup', onMU)
        }
        document.addEventListener('mousemove', onMM)
        document.addEventListener('mouseup', onMU)
      }

      header.addEventListener('mousedown', onDragStart)
      const rh = el.querySelector('.dialog-resize-handle')
      if (rh) rh.addEventListener('mousedown', onResizeStart)

      // When the overlay is removed (dialog closed), clear maximized class
      // so the next time the dialog opens, it starts fresh
      const overlay = el.closest('.el-overlay')
      if (overlay) {
        const cleanupObs = new MutationObserver(() => {
          if (!document.contains(overlay)) {
            el.classList.remove('dialog-maximized', 'dialog-minimized')
            cleanupObs.disconnect()
          }
        })
        cleanupObs.observe(document.body, { childList: true, subtree: true })
      }
    }

    let observer

    const processOverlay = (overlay) => {
      const dialog = overlay.querySelector('.el-dialog')
      if (!dialog || dialog.dataset.draggableInitialized === 'true') return
      const titleEl = dialog.querySelector('.el-dialog__title')
      const title = titleEl?.textContent?.trim() || overlay.getAttribute('aria-label') || ''
      nextTick(() => applyToDialog(dialog, title))
    }

    const isOverlayVisible = (overlay) => {
      const inline = overlay.style.display
      if (inline !== '') return inline !== 'none'
      return window.getComputedStyle(overlay).display !== 'none'
    }

    const processExistingOverlays = () => {
      document.querySelectorAll('.el-overlay').forEach(processOverlay)
    }

    observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
          const overlay = mutation.target
          if (!overlay.classList.contains('el-overlay')) continue
          setTimeout(() => processOverlay(overlay), 50)
          continue
        }
        if (mutation.type === 'childList') {
          for (const node of mutation.addedNodes) {
            if (node.nodeType !== Node.ELEMENT_NODE) continue
            if (node.matches?.('.el-overlay')) {
              setTimeout(() => processOverlay(node), 100)
              continue
            }
            node.querySelectorAll?.('.el-overlay').forEach((overlay) => {
              setTimeout(() => processOverlay(overlay), 100)
            })
          }
        }
      }
    })

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['style'],
    })

    const pollInterval = setInterval(() => {
      document.querySelectorAll('.el-dialog:not([data-draggable-initialized])').forEach((dialog) => {
        const overlay = dialog.closest('.el-overlay')
        if (overlay && isOverlayVisible(overlay)) {
          processOverlay(overlay)
        }
      })
    }, 300)

    nextTick(() => {
      processExistingOverlays()
    })
  },
}
