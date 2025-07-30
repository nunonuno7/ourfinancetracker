document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 [drag_reorder.js] Initializing...');

    // More flexible selector - find all tables with sortable capability
    const sortableTables = document.querySelectorAll('.sortable-table, tbody[data-reorder-url]');

    sortableTables.forEach(table => {
        const reorderUrl = table.dataset.reorderUrl;
        if (!reorderUrl) {
            console.warn('⚠️ [drag_reorder.js] No reorder URL found for table:', table);
            return;
        }

        console.log(`🎯 [drag_reorder.js] Setting up sortable for table with URL: ${reorderUrl}`);

        // Enhanced sortable configuration
        const sortable = new Sortable(table, {
            handle: '.handle',
            animation: 150,
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            dragClass: 'sortable-drag',
            // Make sure we can drag table rows
            draggable: 'tr.form-row, tr[data-id], tr.draggable-row',
            // Prevent dragging if no handle or data-id
            filter: function(evt, item) {
                const hasHandle = item.querySelector('.handle');
                const hasDataId = item.hasAttribute('data-id') || item.querySelector('[name$="-account"]');
                const isAccountRow = item.classList.contains('draggable-row');
                
                // For account list rows, only check for handle and data-id
                if (isAccountRow) {
                    if (!hasHandle) {
                        console.warn('⚠️ [drag_reorder.js] Account row missing handle:', item);
                    }
                    if (!hasDataId) {
                        console.warn('⚠️ [drag_reorder.js] Account row missing data-id:', item);
                    }
                    return !hasHandle || !hasDataId;
                }
                
                // For balance form rows, check for form fields
                if (!hasHandle) {
                    console.warn('⚠️ [drag_reorder.js] Row missing handle:', item);
                }
                if (!hasDataId) {
                    console.warn('⚠️ [drag_reorder.js] Row missing data-id or account field:', item);
                }
                
                return !hasHandle || !hasDataId;
            },
            onStart: function(evt) {
                console.log('🎯 [drag_reorder.js] Drag started on:', evt.item);
            },
            onEnd: function(evt) {
                console.log('📝 [drag_reorder.js] Drag ended:', evt);

                // Get all draggable rows (not just ones with data-id)
                const rows = table.querySelectorAll('tr.form-row, tr[data-id], tr.draggable-row');
                const orderData = [];

                rows.forEach((row, index) => {
                    let id = row.dataset.id;
                    
                    // For account list rows, data-id should always be present
                    if (row.classList.contains('draggable-row')) {
                        if (id) {
                            orderData.push({
                                id: id,
                                position: index
                            });
                        } else {
                            console.warn('⚠️ [drag_reorder.js] Account row missing data-id:', row);
                        }
                        return;
                    }
                    
                    // If no data-id, try to get from form field (for balance forms)
                    if (!id) {
                        const accountField = row.querySelector('[name$="-account"]');
                        const idField = row.querySelector('[name$="-id"]');
                        
                        if (idField && idField.value) {
                            id = idField.value;
                        } else if (accountField) {
                            // For new rows, use a temporary identifier
                            id = `new_${index}_${accountField.value || 'unnamed'}`;
                        }
                    }
                    
                    if (id) {
                        orderData.push({
                            id: id,
                            position: index
                        });
                    }
                });

                if (orderData.length === 0) {
                    console.warn('⚠️ [drag_reorder.js] No valid rows found for reordering');
                    return;
                }

                console.log('📊 [drag_reorder.js] New order:', orderData);

                // Send update to server
                fetch(reorderUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        order: orderData
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        console.log('✅ [drag_reorder.js] Order updated successfully');
                        showToast('Position updated successfully!', 'success');
                    } else {
                        console.error('❌ [drag_reorder.js] Failed to update order:', data.error);
                        showToast('Failed to update position: ' + (data.error || 'Unknown error'), 'error');
                    }
                })
                .catch(error => {
                    console.error('❌ [drag_reorder.js] Network error:', error);
                    showToast('Network error occurred', 'error');
                });
            }
        });

        // Add visual feedback for draggable elements
        const draggableRows = table.querySelectorAll('tr.form-row, tr[data-id], tr.draggable-row');
        draggableRows.forEach(row => {
            const handle = row.querySelector('.handle');
            if (handle) {
                handle.style.cursor = 'grab';
                handle.addEventListener('mousedown', () => {
                    handle.style.cursor = 'grabbing';
                });
                handle.addEventListener('mouseup', () => {
                    handle.style.cursor = 'grab';
                });
            }
        });
    });

    function getCsrfToken() {
        // Try multiple methods to get CSRF token
        let token = null;

        // Method 1: From meta tag
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            token = metaTag.getAttribute('content');
        }

        // Method 2: From cookie
        if (!token) {
            const cookies = document.cookie.split(';');
            for (let cookie of cookies) {
                const [name, value] = cookie.trim().split('=');
                if (name === 'csrftoken') {
                    token = value;
                    break;
                }
            }
        }

        // Method 3: From Django template (if available)
        if (!token && window.csrfToken) {
            token = window.csrfToken;
        }

        // Method 4: From hidden input
        if (!token) {
            const hiddenInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
            if (hiddenInput) {
                token = hiddenInput.value;
            }
        }

        console.log('🔐 [drag_reorder.js] CSRF token found:', token ? 'Yes' : 'No');
        return token;
    }

    function showToast(message, type = 'info') {
        // Simple toast notification
        const toast = document.createElement('div');
        toast.className = `alert alert-${type === 'error' ? 'danger' : 'success'} position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 250px;';
        toast.textContent = message;

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    // Listen for requests to reinitialize sortable (when new rows are added)
    document.addEventListener('reinitializeSortable', function() {
        console.log('🔄 [drag_reorder.js] Reinitializing sortable...');
        
        // Find any new sortable tables that weren't initialized
        const newSortableTables = document.querySelectorAll('.sortable-table:not([data-sortable-initialized]), tbody[data-reorder-url]:not([data-sortable-initialized])');
        
        newSortableTables.forEach(table => {
            const reorderUrl = table.dataset.reorderUrl;
            if (reorderUrl) {
                console.log(`🎯 [drag_reorder.js] Initializing new sortable table`);
                
                new Sortable(table, {
                    handle: '.handle',
                    animation: 150,
                    ghostClass: 'sortable-ghost',
                    chosenClass: 'sortable-chosen',
                    dragClass: 'sortable-drag',
                    draggable: 'tr.form-row, tr[data-id], tr.draggable-row',
                    filter: function(evt, item) {
                        const hasHandle = item.querySelector('.handle');
                        const hasDataId = item.hasAttribute('data-id') || item.querySelector('[name$="-account"]');
                        const isAccountRow = item.classList.contains('draggable-row');
                        
                        // For account list rows, only check for handle and data-id
                        if (isAccountRow) {
                            return !hasHandle || !hasDataId;
                        }
                        
                        return !hasHandle || !hasDataId;
                    },
                    onEnd: function(evt) {
                        // Same logic as above
                        const rows = table.querySelectorAll('tr.form-row, tr[data-id], tr.draggable-row');
                        const orderData = [];

                        rows.forEach((row, index) => {
                            let id = row.dataset.id;
                            
                            // For account list rows, data-id should always be present
                            if (row.classList.contains('draggable-row')) {
                                if (id) {
                                    orderData.push({
                                        id: id,
                                        position: index
                                    });
                                }
                                return;
                            }
                            
                            // For balance form rows
                            if (!id) {
                                const accountField = row.querySelector('[name$="-account"]');
                                const idField = row.querySelector('[name$="-id"]');
                                
                                if (idField && idField.value) {
                                    id = idField.value;
                                } else if (accountField) {
                                    id = `new_${index}_${accountField.value || 'unnamed'}`;
                                }
                            }
                            
                            if (id) {
                                orderData.push({
                                    id: id,
                                    position: index
                                });
                            }
                        });

                        if (orderData.length > 0) {
                            fetch(reorderUrl, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': getCsrfToken()
                                },
                                body: JSON.stringify({
                                    order: orderData
                                })
                            })
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    showToast('Position updated successfully!', 'success');
                                } else {
                                    showToast('Failed to update position: ' + (data.error || 'Unknown error'), 'error');
                                }
                            })
                            .catch(error => {
                                showToast('Network error occurred', 'error');
                            });
                        }
                    }
                });
                
                // Mark as initialized
                table.setAttribute('data-sortable-initialized', 'true');
            }
        });
    });
});