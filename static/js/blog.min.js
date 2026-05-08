// 1. RUN ON PAGE LOAD: Check cookies to highlight posts already liked/shard
document.addEventListener('DOMContentLoaded', function () {
    console.log("Blog JS initialized.");
    console.log("Share buttons found:", document.querySelectorAll('.action-share').length);
    const shareBtn = document.querySelector('.action-share');
    if (shareBtn) {
        console.log("Share button visibility:", getComputedStyle(shareBtn).visibility);
        console.log("Share button display:", getComputedStyle(shareBtn).display);
        console.log("Share button opacity:", getComputedStyle(shareBtn).opacity);
    }

    document.querySelectorAll('.like-btn:not(.comment-like-btn)').forEach(btn => {
        const postId = btn.getAttribute('data-id');
        // Check if a cookie exists for this post
        if (document.cookie.includes(`liked_post_${postId}=`)) {
            const icon = btn.querySelector('i');
            if (icon) icon.classList.replace('fa-regular', 'fa-solid');
            btn.style.color = "#e74c3c";
            btn.classList.add('voted');
        }
    });

    document.querySelectorAll('.comment-like-btn').forEach(btn => {
        const commentId = btn.getAttribute('data-id');
        if (document.cookie.includes(`liked_comment_${commentId}=`)) {
            const icon = btn.querySelector('i');
            if (icon) icon.classList.replace('fa-regular', 'fa-solid');
            btn.style.color = "#e74c3c";
            btn.classList.add('voted');
        }
    });

    document.querySelectorAll('.action-share').forEach(btn => {
        const postId = btn.getAttribute('data-id');
        // Check if a cookie exists for this post
        if (document.cookie.includes(`shared_post_${postId}=`)) {
            btn.classList.add('shared');
        }
    });
});

// 2. CLICK HANDLER: Using Event Delegation (Bulletproof)
document.addEventListener('click', function (event) {
    const btn = event.target.closest('.like-btn');

    if (btn && !btn.classList.contains('comment-like-btn')) {
        event.preventDefault();
        event.stopPropagation();

        const postId = btn.getAttribute('data-id');
        const countSpan = btn.querySelector('.count');
        const icon = btn.querySelector('i');

        console.log("Attempting like for ID:", postId);

        // Optimistic UI update
        const wasLiked = btn.classList.contains('voted');
        const currentCount = parseInt(countSpan.innerText, 10);

        if (wasLiked) {
            // Optimistically unlike
            countSpan.innerText = currentCount - 1;
            if (icon) icon.classList.replace('fa-solid', 'fa-regular');
            btn.style.color = "";
            btn.classList.remove('voted');
        } else {
            // Optimistically like
            countSpan.innerText = currentCount + 1;
            if (icon) icon.classList.replace('fa-regular', 'fa-solid');
            btn.style.color = "#e74c3c";
            btn.classList.add('voted');
        }

        // Disable button until server responds
        btn.disabled = true;

        fetch('/like/' + postId, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
            .then(response => response.json())
            .then(data => {
                console.log("Server Response:", data);

                if (data.success === true) {
                    // SUCCESS: Update count and UI for like buttons with this postId
                    document.querySelectorAll(`.like-btn[data-id="${postId}"] .count`).forEach(span => span.innerText = data.new_count);

                    // Update UI based on liked status
                    if (data.liked === true) {
                        // Liked: turn solid, red, add voted class
                        document.querySelectorAll(`.like-btn[data-id="${postId}"]`).forEach(b => {
                            const i = b.querySelector('i');
                            if (i) i.classList.replace('fa-regular', 'fa-solid');
                            b.style.color = "#e74c3c";
                            b.classList.add('voted');
                        });
                        // Google Analytics Event: Like
                        if (typeof gtag === 'function') {
                            gtag('event', 'blog_like', {
                                'post_id': postId,
                                'action': 'like'
                            });
                        }
                    } else {
                        // Unliked: turn regular, default color, remove voted class
                        document.querySelectorAll(`.like-btn[data-id="${postId}"]`).forEach(b => {
                            const i = b.querySelector('i');
                            if (i) i.classList.replace('fa-solid', 'fa-regular');
                            b.style.color = ""; // Reset to default
                            b.classList.remove('voted');
                        });
                        // Google Analytics Event: Unlike
                        if (typeof gtag === 'function') {
                            gtag('event', 'blog_like', {
                                'post_id': postId,
                                'action': 'unlike'
                            });
                        }
                    }
                }

                // Re-enable button
                btn.disabled = false;

                if (data.success === false) {
                    // FAILURE: Revert optimistic update
                    console.log("Like failed: " + data.message);
                    if (wasLiked) {
                        // Revert to liked
                        countSpan.innerText = currentCount;
                        if (icon) icon.classList.replace('fa-regular', 'fa-solid');
                        btn.style.color = "#e74c3c";
                        btn.classList.add('voted');
                    } else {
                        // Revert to unliked
                        countSpan.innerText = currentCount;
                        if (icon) icon.classList.replace('fa-solid', 'fa-regular');
                        btn.style.color = "";
                        btn.classList.remove('voted');
                    }
                }
            })
            .catch(error => {
                console.error("Fetch Error:", error);
                // Revert optimistic update on error
                if (wasLiked) {
                    countSpan.innerText = currentCount;
                    if (icon) icon.classList.replace('fa-regular', 'fa-solid');
                    btn.style.color = "#e74c3c";
                    btn.classList.add('voted');
                } else {
                    countSpan.innerText = currentCount;
                    if (icon) icon.classList.replace('fa-solid', 'fa-regular');
                    btn.style.color = "";
                    btn.classList.remove('voted');
                }
                // Re-enable button
                btn.disabled = false;
            });
    }

    // Check for Comment Like Button Click
    const commentLikeBtn = event.target.closest('.comment-like-btn');
    if (commentLikeBtn) {
        event.preventDefault();
        event.stopPropagation();

        const commentId = commentLikeBtn.getAttribute('data-id');
        const countSpan = commentLikeBtn.querySelector('.count');
        const icon = commentLikeBtn.querySelector('i');
        const wasLiked = commentLikeBtn.classList.contains('voted');
        const currentCount = parseInt(countSpan.innerText, 10);

        if (wasLiked) {
            countSpan.innerText = currentCount - 1;
            if (icon) icon.classList.replace('fa-solid', 'fa-regular');
            commentLikeBtn.style.color = "";
            commentLikeBtn.classList.remove('voted');
        } else {
            countSpan.innerText = currentCount + 1;
            if (icon) icon.classList.replace('fa-regular', 'fa-solid');
            commentLikeBtn.style.color = "#e74c3c";
            commentLikeBtn.classList.add('voted');
        }

        commentLikeBtn.disabled = true;

        fetch('/like/comment/' + commentId, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    countSpan.innerText = data.new_count;
                    if (data.liked) {
                        if (icon) icon.classList.replace('fa-regular', 'fa-solid');
                        commentLikeBtn.style.color = "#e74c3c";
                        commentLikeBtn.classList.add('voted');
                    } else {
                        if (icon) icon.classList.replace('fa-solid', 'fa-regular');
                        commentLikeBtn.style.color = "";
                        commentLikeBtn.classList.remove('voted');
                    }
                } else {
                    countSpan.innerText = currentCount;
                    if (wasLiked) { if (icon) icon.classList.replace('fa-regular', 'fa-solid'); commentLikeBtn.style.color = "#e74c3c"; commentLikeBtn.classList.add('voted'); }
                    else { if (icon) icon.classList.replace('fa-solid', 'fa-regular'); commentLikeBtn.style.color = ""; commentLikeBtn.classList.remove('voted'); }
                }
                commentLikeBtn.disabled = false;
            })
            .catch(() => {
                countSpan.innerText = currentCount;
                if (wasLiked) { if (icon) icon.classList.replace('fa-regular', 'fa-solid'); commentLikeBtn.style.color = "#e74c3c"; commentLikeBtn.classList.add('voted'); }
                else { if (icon) icon.classList.replace('fa-solid', 'fa-regular'); commentLikeBtn.style.color = ""; commentLikeBtn.classList.remove('voted'); }
                commentLikeBtn.disabled = false;
            });
    }

    // Check for Share Button Click
    const shareBtn = event.target.closest('.action-share');
    if (shareBtn) {
        event.preventDefault();

        const postId = shareBtn.getAttribute('data-id');
        const countSpan = shareBtn.querySelector('.count');

        console.log("Attempting share for ID:", postId);

        // Optimistic UI update - only increment if not already shared
        const currentCount = parseInt(countSpan.innerText, 10);
        const alreadyShared = shareBtn.classList.contains('shared');
        if (!alreadyShared) {
            countSpan.innerText = currentCount + 1;
            shareBtn.classList.add('shared');
        }

        // Disable button until server responds
        shareBtn.disabled = true;

        fetch('/share/' + postId, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
            .then(response => response.json())
            .then(data => {
                console.log("Share Server Response:", data);

                if (data.success === true) {
                    // SUCCESS: Update count and copy link
                    document.querySelectorAll(`.action-share[data-id="${postId}"] .count`).forEach(span => span.innerText = data.new_count);
                    document.querySelectorAll(`.action-share[data-id="${postId}"]`).forEach(b => b.classList.add('shared'));

                    // Google Analytics Event: Share
                    if (typeof gtag === 'function') {
                        gtag('event', 'blog_share', {
                            'post_id': postId,
                            'method': 'copy_link'
                        });
                    }

                    // Get the specific post URL from data-url attribute
                    const url = shareBtn.getAttribute('data-url') || window.location.href;

                    // Use the Browser Clipboard API
                    navigator.clipboard.writeText(url).then(() => {
                        // Visual Feedback: Change icon and text
                        const originalContent = shareBtn.innerHTML;
                        shareBtn.innerHTML = '<i class="fa-solid fa-check"></i> <span>Copied!</span>';
                        shareBtn.classList.add('share-success');

                        // Reset the button after 2 seconds
                        setTimeout(() => {
                            shareBtn.innerHTML = originalContent;
                            shareBtn.classList.remove('share-success');
                            shareBtn.disabled = false;
                        }, 2000);
                    }).catch(err => {
                        console.error('Could not copy text: ', err);
                    });
                } else {
                    // BLOCKED: Revert optimistic update and copy link
                    console.log("Share blocked: " + data.message);
                    countSpan.innerText = currentCount;
                    shareBtn.classList.remove('shared');

                    const url = shareBtn.getAttribute('data-url') || window.location.href;
                    navigator.clipboard.writeText(url).then(() => {
                        shareBtn.innerHTML = '<i class="fa-solid fa-check"></i> <span>Copied!</span>';
                        shareBtn.classList.add('share-success');
                        setTimeout(() => {
                            shareBtn.innerHTML = '<i class="fa-solid fa-share-nodes"></i> <span class="count">' + countSpan.innerText + '</span>';
                            shareBtn.classList.remove('share-success');
                            shareBtn.disabled = false;
                        }, 2000);
                    });
                }
            })
            .catch(error => {
                console.error("Share Fetch Error:", error);
                // Revert optimistic update
                countSpan.innerText = currentCount;
                shareBtn.classList.remove('shared');
                // Re-enable button
                shareBtn.disabled = false;
            });
    }

    // Check for Comment Button Click
    const commentBtn = event.target.closest('button[title="Comment"]');
    if (commentBtn) {
        event.preventDefault();
        console.log("Comment button clicked, attempting to scroll to comments.");
        const commentsSection = document.getElementById('comments');
        if (commentsSection) {
            console.log("Comments section found, scrolling.");
            commentsSection.scrollIntoView({ behavior: 'smooth' });
        } else {
            console.log("Comments section not found.");
        }
    }
});

// Track anchor link clicks (e.g., footnotes) for traffic logs
document.addEventListener('click', function (event) {
    const anchor = event.target.closest('a[href^="#"]');
    if (anchor) {
        const href = anchor.getAttribute('href');
        if (href && href !== '#') {
            const fullUrl = window.location.origin + window.location.pathname + href;
            fetch('/log_event?url=' + encodeURIComponent(fullUrl) + '&_cb=' + Date.now());
        }
    }
});

// Initial page load ping (captures blog visits even if edge-cached)
fetch('/log_event?url=' + encodeURIComponent(window.location.href) + '&_cb=' + Date.now());

