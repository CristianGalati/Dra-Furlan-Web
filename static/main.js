document.addEventListener('DOMContentLoaded', () => {
    // Busca el botón por id o por sus clases habituales (.btn-mp, .btn-mp-pay)
    const btnPagar = document.getElementById('btn-guardar-pagar') || document.querySelector('.btn-mp') || document.querySelector('.btn-mp-pay');

    if (btnPagar) {
        btnPagar.addEventListener('click', async (e) => {
            e.preventDefault();

            // Guardar el texto original para restaurarlo si falla el proceso
            const textoOriginal = btnPagar.innerHTML;

            // 1. Deshabilitar botón y activar el Spinner CSS
            btnPagar.disabled = true;
            btnPagar.innerHTML = `<span class="spinner"></span> Cargando Mercado Pago...`;

            try {
                // 2. Solicitar la preferencia de pago al backend Flask
                const response = await fetch('/crear-preferencia', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const data = await response.json();

                if (data.init_point) {
                    // 3. Redirigir al checkout oficial de Mercado Pago
                    window.location.href = data.init_point;
                } else {
                    alert('Error al iniciar el pago. Revisa las credenciales de Mercado Pago.');
                    // Restaurar el botón
                    btnPagar.disabled = false;
                    btnPagar.innerHTML = textoOriginal;
                }
            } catch (error) {
                console.error('Error:', error);
                alert('No se pudo conectar con el servidor.');
                // Restaurar el botón en caso de falla de red/servidor
                btnPagar.disabled = false;
                btnPagar.innerHTML = textoOriginal;
            }
        });
    }
});