document.querySelectorAll('[data-search]').forEach(input=>{
  input.addEventListener('input',()=>{
    const query=input.value.trim().toLocaleLowerCase();let matches=0;
    document.querySelectorAll('.searchable').forEach(item=>{const found=item.dataset.searchText.toLocaleLowerCase().includes(query);item.hidden=!found;if(found)matches++;});
    document.querySelectorAll('.curriculum-section').forEach(section=>{section.hidden=![...section.querySelectorAll('.searchable')].some(item=>!item.hidden);});
    const empty=document.querySelector('.search-empty');if(empty)empty.hidden=matches>0;
  });
});
document.querySelectorAll('[data-copy]').forEach(button=>{
  button.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(button.dataset.copy);button.textContent='Copied ✓';setTimeout(()=>button.textContent='Copy example',2000);}catch{button.textContent='Select the example above to copy';}});
});
document.querySelectorAll('.practice-form').forEach(form=>{
  form.addEventListener('submit',async event=>{
    event.preventDefault();const feedback=form.parentElement.querySelector('.practice-feedback');const button=form.querySelector('button');button.disabled=true;feedback.textContent='Checking your answer…';
    try{const response=await fetch(`/lesson/${form.dataset.lesson}/practice`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content},body:JSON.stringify({answer:form.elements.answer.value})});if(!response.ok)throw new Error('Unable to save this answer. Reload the page and try again.');const data=await response.json();feedback.textContent=data.message;feedback.className=`practice-feedback feedback ${data.correct?'success':'failure'}`;}
    catch(error){feedback.textContent=error.message||'Could not connect. Check that the local app is running and try again.';feedback.className='practice-feedback feedback failure';}
    finally{button.disabled=false;}
  });
});
