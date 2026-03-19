// static/js/main.js

document.addEventListener("DOMContentLoaded", function () {
    // Переключение вход / регистрация
    const loginBlock = document.getElementById("login-form-block");
    const registerBlock = document.getElementById("register-form-block");

    const showRegisterLink = document.getElementById("show-register");
    const backToLoginBtn = document.getElementById("back-to-login");

    if (showRegisterLink && loginBlock && registerBlock) {
        showRegisterLink.addEventListener("click", function (e) {
            e.preventDefault();
            loginBlock.classList.remove("active");
            registerBlock.classList.add("active");
        });
    }

    if (backToLoginBtn && loginBlock && registerBlock) {
        backToLoginBtn.addEventListener("click", function () {
            registerBlock.classList.remove("active");
            loginBlock.classList.add("active");
        });
    }

    // Карусель товаров на главной
    const carouselButtons = document.querySelectorAll(".carousel-btn");
    carouselButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            const targetSelector = btn.getAttribute("data-target");
            const direction = btn.getAttribute("data-direction");
            const container = document.querySelector(targetSelector);
            if (!container) return;

            const scrollAmount = 260; // px
            if (direction === "left") {
                container.scrollBy({ left: -scrollAmount, behavior: "smooth" });
            } else {
                container.scrollBy({ left: scrollAmount, behavior: "smooth" });
            }
        });
    });

    // Переключение картинок на карточке товара
    const mainImage = document.getElementById("main-product-image");
    const thumbs = document.querySelectorAll(".product-thumb-img");

    if (mainImage && thumbs.length > 0) {
        thumbs.forEach(function (thumb) {
            thumb.addEventListener("click", function () {
                const fullSrc = thumb.getAttribute("data-full");
                if (fullSrc) {
                    mainImage.setAttribute("src", fullSrc);
                }
            });
        });
    }
});
