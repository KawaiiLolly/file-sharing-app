        const passwordInput = document.getElementById('id_password');
        const toggleButton = document.getElementById('toggle-password');

        toggleButton.addEventListener('mousedown', function (e) {
            e.preventDefault();
            passwordInput.type = 'text';
        });

        toggleButton.addEventListener('mouseup', function () {
            passwordInput.type = 'password';
        });

        toggleButton.addEventListener('mouseleave', function () {
            passwordInput.type = 'password';
        });
    </script>
