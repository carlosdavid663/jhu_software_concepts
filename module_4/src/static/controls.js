// Run this function when either button's form is submitted.
async function submitDataForm(event) {
  // Keep the browser on the Analysis page while we send the request.
  event.preventDefault();
  const form = event.currentTarget;
  const buttons = document.querySelectorAll('.controls button');

  for (const button of buttons) {
    button.disabled = true;
  }

  try {
    // await waits for the server's reply. POST asks it to perform an action.
    await fetch(form.action, {
      method: 'POST',
      headers: {'Accept': 'application/json'}
    });
    window.location.replace('/analysis');
  } catch (error) {
    const statusMessage = document.querySelector('[role="status"]');
    statusMessage.textContent = 'Connection interrupted. Refresh the page to check progress.';
    for (const button of buttons) {
      button.disabled = false;
    }
  }
}

// Attach the same function to Pull Data and Update Analysis.
const forms = document.querySelectorAll('.controls form');
for (const form of forms) {
  form.addEventListener('submit', submitDataForm);
}
