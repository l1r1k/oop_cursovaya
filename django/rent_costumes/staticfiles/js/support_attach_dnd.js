/**
 * Drag-and-drop для прикрепления изображений в чате поддержки.
 */
const SupportAttachDnd = {
    ALLOWED_TYPES: ['image/jpeg', 'image/png', 'image/webp', 'image/jpg'],

    isImageFile(file) {
        return file && this.ALLOWED_TYPES.includes(file.type);
    },

    filterImages(fileList) {
        return Array.from(fileList || []).filter((file) => this.isImageFile(file));
    },

    /**
     * @param {Object} options
     * @param {HTMLElement[]} options.zones
     * @param {function(File[]):void} options.onFiles
     * @param {function():number} options.getCount
     * @param {number} [options.maxFiles=5]
     */
    setup({ zones, onFiles, getCount, maxFiles = 5 }) {
        zones.filter(Boolean).forEach((zone) => {
            zone.addEventListener('dragenter', (e) => {
                e.preventDefault();
                zone.classList.add('support-drop-active');
            });
            zone.addEventListener('dragover', (e) => {
                e.preventDefault();
                zone.classList.add('support-drop-active');
            });
            zone.addEventListener('dragleave', (e) => {
                if (!zone.contains(e.relatedTarget)) {
                    zone.classList.remove('support-drop-active');
                }
            });
            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                zone.classList.remove('support-drop-active');
                const images = this.filterImages(e.dataTransfer?.files);
                if (!images.length) {
                    if (typeof showNotification === 'function') {
                        showNotification('Перетащите только изображения (JPEG, PNG, WEBP)', 'warning');
                    }
                    return;
                }
                const current = getCount ? getCount() : 0;
                const allowed = Math.max(0, maxFiles - current);
                if (allowed <= 0) {
                    if (typeof showNotification === 'function') {
                        showNotification(`Не более ${maxFiles} изображений`, 'warning');
                    }
                    return;
                }
                onFiles(images.slice(0, allowed));
            });
        });
    },
};
