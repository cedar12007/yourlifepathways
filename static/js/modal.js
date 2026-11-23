
// Modal Helper Functions (Added by Antigravity)
let modalTimer; // Variable to store the timer ID

function showModal(message, isSuccess) {
    const modal = document.getElementById("statusModal");
    const modalMessage = document.getElementById("modalMessage");

    if (modal && modalMessage) {
        // Clear any existing timer to prevent overlaps
        if (modalTimer) clearTimeout(modalTimer);

        modalMessage.textContent = message;
        modal.style.display = "block";

        if (isSuccess) {
            // Disappear after 5 seconds
            modalTimer = setTimeout(function () {
                closeModal(); // Use a shared close function
            }, 5000);
        }
    }
}

function closeModal() {
    const modal = document.getElementById("statusModal");
    const modalMessage = document.getElementById("modalMessage");

    if (modal) {
        modal.style.display = "none";

        // Clear the timer if it's running (e.g. manual close)
        if (modalTimer) clearTimeout(modalTimer);

        const form = document.querySelector("#contactForm, #commentForm");
        if (form) form.reset();

        // Reload logic for both blog comments and admin moderation actions
        const isBlogPage = window.location.pathname.includes('/blog/');
        const isAdminPage = window.location.pathname.includes('/admin/');
        const isSuccessMessage = modalMessage && (
            modalMessage.textContent.includes("Thank you") ||
            modalMessage.textContent.includes("successfully") ||
            modalMessage.textContent.includes("Comment approved") ||
            modalMessage.textContent.includes("Comment unapproved") ||
            modalMessage.textContent.includes("Comment archived") ||
            modalMessage.textContent.includes("Comment restored")
        );

        if (isSuccessMessage && (isBlogPage || isAdminPage)) {
            window.location.reload();
        }
    }
}

// Global handler for admin AJAX actions
async function handleAjaxAction(event, form) {
    event.preventDefault();
    try {
        const response = await fetch(form.action, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        const data = await response.json();
        showModal(data.message, data.success);
    } catch (error) {
        console.error("Action error:", error);
        showModal("An error occurred. Please try again.", false);
    }
}

function initModal() {
    // Get modal elements
    const modal = document.getElementById("statusModal");
    if (!modal) return;

    // Only target close-btn inside statusModal, never global close-btn
    const span = modal.querySelector(".close-btn");
    if (span) {
        span.onclick = function () {
            closeModal();
        };
    }

    // Close modal when clicking outside
    window.addEventListener('click', function (event) {
        if (event.target === modal) {
            closeModal();
        }
    });
}

// Initialize on load
document.addEventListener('DOMContentLoaded', initModal);

// --- Flash Message Handling (Legacy/Server-side support) ---
function closeFlash(element) {
    if (!element) return;
    element.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
    element.style.opacity = '0';
    element.style.transform = 'scale(0.95)';
    setTimeout(() => {
        if (element && element.parentNode) {
            element.parentNode.removeChild(element);
        }
    }, 250);
}

// Reliable click handler for any flash modal close button via event delegation
document.addEventListener('click', function (event) {
    const closeBtn = event.target.closest('#flash-container .close-btn, .flash-modal .close-btn');
    if (closeBtn) {
        event.preventDefault();
        event.stopPropagation();
        const flashModal = closeBtn.closest('.flash-modal');
        if (flashModal) {
            closeFlash(flashModal);
        }
    }
});

// Auto-hide flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
        const modals = document.querySelectorAll('.flash-modal');
        modals.forEach(modal => closeFlash(modal));
    }, 5000);
});
