let token;
let urls = [];
const status = document.querySelector('#status');
const downloads = document.querySelector('#downloads');
function clearOutput() {
  urls.forEach(url => URL.revokeObjectURL(url)); urls = [];
  downloads.replaceChildren(); status.textContent = ''; status.className = '';
}
document.querySelectorAll('nav button').forEach(button => button.addEventListener('click', () => {
  clearOutput();
  document.querySelectorAll('form').forEach(form => { form.hidden = form.id !== button.dataset.panel; });
  document.querySelectorAll('nav button').forEach(item => {
    const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active));
  });
  document.querySelectorAll('input[type=password]').forEach(input => { input.value = ''; });
}));
async function readFile(id, limit) {
  const file = document.getElementById(id).files[0];
  if (!file) throw Error('Select all required files.');
  if (file.size > limit) throw Error('Selected file exceeds the allowed size.');
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(binary);
}
function download(data, name, label) {
  const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], {type:'application/octet-stream'})); urls.push(url);
  const link = document.createElement('a'); link.href = url; link.download = name; link.textContent = label; downloads.append(link);
}
document.querySelectorAll('form').forEach(form => form.addEventListener('submit', async event => {
  event.preventDefault(); clearOutput();
  document.querySelectorAll('button').forEach(button => { button.disabled = true; });
  status.textContent = 'Processing securely on your local Python server…';
  try {
    if (!token) {
      const session = await fetch('/session', {cache:'no-store'});
      if (!session.ok) throw Error('Cannot connect to the local server.');
      token = (await session.json()).token;
    }
    let args;
    if (form.id === 'keys') {
      const password = document.querySelector('#key-password').value;
      if (password !== document.querySelector('#confirm').value) throw Error('Passwords do not match.');
      args = {password};
    } else if (form.id === 'encrypt') {
      args = {key:await readFile('public-key', 16384), file:await readFile('plain-file', 10*1024*1024)};
    } else {
      args = {key:await readFile('private-key', 16384), file:await readFile('encrypted-file', 10*1024*1024+2048), password:document.querySelector('#unlock-password').value};
    }
    const response = await fetch('/api/' + form.id, {method:'POST', headers:{'Content-Type':'application/json', 'X-PQC-Token':token}, body:JSON.stringify(args)});
    const result = await response.json();
    if (!response.ok) throw Error(result.error || 'Processing failed.');
    if (form.id === 'keys') {
      download(result.public, 'pqc-public.pem', 'Download public key');
      download(result.private, 'pqc-private.pem', 'Download protected private key');
      status.textContent = 'Key pair ready. Save both keys now. Public-key SHA-256 fingerprint: ' + result.fingerprint;
    } else if (form.id === 'encrypt') {
      const name = document.querySelector('#plain-file').files[0].name;
      download(result.file, name + '.pqc', 'Download encrypted file');
      status.textContent = 'File encrypted. Recipient fingerprint: ' + result.fingerprint;
    } else {
      const name = document.querySelector('#encrypted-file').files[0].name.replace(/\.pqc$/i, '');
      download(result.file, 'restored-' + (name || 'file'), 'Download decrypted file');
      status.textContent = 'File decrypted and integrity verified.';
    }
    document.querySelectorAll('input[type=password]').forEach(input => { input.value = ''; });
  } catch (error) { status.className = 'error'; status.textContent = error.message; }
  finally { document.querySelectorAll('button').forEach(button => { button.disabled = false; }); }
}));
