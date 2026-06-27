document.getElementById('flashForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData);
    
    const output = document.getElementById('output');
    output.innerHTML = '<span class="info">[*] SYNCING WITH SQR400.PY + RECEIVER PROFILE...</span><br>';
    
    setTimeout(() => { 
        output.innerHTML += '<span class="info">[*] VALIDATING RECEIVER DETAILS...</span><br>'; 
    }, 400);
    
    try {
        const res = await fetch('/flash', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const json = await res.json();
        
        setTimeout(() => {
            output.innerHTML += `<span class="success">[+] PIN & RECEIVER AUTHORIZED SUCCESSFULLY</span><br>`;
            output.innerHTML += `<span class="info">[*] EXECUTING ${data.type.toUpperCase()} TRANSFER | ${parseFloat(data.amount).toLocaleString()} ${data.currency}</span><br>`;
            output.innerHTML += `    SENDER: Aulia Muji Hardiansyah (BSMDIDJAXXX)<br>`;
            output.innerHTML += `    RECEIVER BANK: ${data.bank_name || 'N/A'} | BIC: ${data.bic}<br>`;
            output.innerHTML += `    ACCOUNT: ${data.account_number} | HOLDER: ${data.account_holder}<br>`;
            output.innerHTML += `    BANK ADDRESS: ${data.bank_address}<br>`;
            output.innerHTML += `    PROTOCOL: ${data.type} • SERVER: BSI-JAKARTA-RELAY<br>`;
            output.innerHTML += `<span class="success">[+++] FLASH TRANSFER COMPLETE - SETTLED VIA BSI RELAY</span><br>`;
            output.innerHTML += `<span class="success">[+++] SETTLEMENT ID: ${Math.random().toString(36).substring(2,20).toUpperCase()}</span><br>`;
            output.innerHTML += `<span class="info">[*] ${data.currency} FUNDS ENROUTE TO RECEIVER - CREDIT WITHIN 30-90 MINUTES</span><br>`;
            output.innerHTML += `<span class="success">[LOG] ${json.output ? json.output.substring(0,180) : 'OPERATION SUCCESS'}</span><br>`;
            document.getElementById('trace').textContent = json.trace || `BSI-2026-${Date.now()}`;
        }, 1300);
    } catch (err) {
        output.innerHTML += `<span class="error">[!] EXECUTION ERROR: ${err.message}</span><br>`;
    }
});

// Auto-scroll terminal
new MutationObserver(() => {
    const out = document.getElementById('output');
    out.scrollTop = out.scrollHeight;
}).observe(document.getElementById('output'), { childList: true });
