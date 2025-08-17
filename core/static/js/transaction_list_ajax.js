
// Compatibility shim - redirects to the official transaction_list_v2.js
// This ensures any references to transaction_list_ajax.js still work

// Since ES6 modules may not be enabled, we'll use a simple script inclusion approach
// The actual implementation is in transaction_list_v2.js

// If you need to reference this file, it will automatically load the main implementation
(function() {
    // Check if the main TransactionManager is already loaded
    if (typeof TransactionManager === 'undefined') {
        // Create a script element to load the main file
        const script = document.createElement('script');
        script.src = '/static/js/transaction_list_v2.js';
        script.type = 'text/javascript';
        const n = window.CSP_NONCE || null;
        if (n) {
            script.setAttribute('nonce', n);
        }
        // Log when the full implementation is ready (includes actions column)
        script.onload = function() {
            console.log('transaction_list_v2.js loaded with actions column support');
        };
        document.body.appendChild(script);
    }
})();
