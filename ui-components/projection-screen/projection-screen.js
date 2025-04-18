document.addEventListener('DOMContentLoaded', function() {
    // Get the button and projection screen elements
    const showScreenBtn = document.getElementById('showScreen');
    const projectionScreen = document.querySelector('.projection-screen');
    
    // Toggle state to track if screen is shown
    let isScreenShown = false;
    
    // Add click event listener to the button
    showScreenBtn.addEventListener('click', function() {
        if (!isScreenShown) {
            // Show the projection screen
            projectionScreen.classList.add('show');
            showScreenBtn.textContent = 'Hide Projection Screen';
            isScreenShown = true;
        } else {
            // Hide the projection screen
            projectionScreen.classList.remove('show');
            showScreenBtn.textContent = 'Show Projection Screen';
            isScreenShown = false;
        }
    });
});
