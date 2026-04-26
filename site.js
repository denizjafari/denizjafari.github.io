(() => {
  // Replace this with FormSubmit's invisible-email token when available.
  const formSubmitRecipient = "ZG56LmpmckBnbWFpbC5jb20=";

  function initFormSubmitForms() {
    const recipient = atob(formSubmitRecipient);

    document.querySelectorAll("form[data-formsubmit-form]").forEach((form) => {
      form.action = `https://formsubmit.co/${recipient}`;
    });
  }

  function initFormSuccessState() {
    const url = new URL(window.location.href);
    if (url.searchParams.get("sent") !== "1") return;

    document.querySelectorAll("form[data-form-success]").forEach((form) => {
      const message = document.createElement("p");
      message.className = "form-status";
      message.textContent = form.dataset.formSuccess;
      form.prepend(message);
    });

    url.searchParams.delete("sent");
    const search = url.searchParams.toString();
    const nextUrl = `${url.pathname}${search ? `?${search}` : ""}${url.hash}`;
    window.history.replaceState({}, document.title, nextUrl);
  }

  document.addEventListener("DOMContentLoaded", () => {
    initFormSubmitForms();
    initFormSuccessState();
  });
})();
