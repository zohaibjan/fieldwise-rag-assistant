const $=(id)=>document.getElementById(id);
async function loadDocuments(){
  const response=await fetch("/api/documents");if(!response.ok)throw Error("Document index unavailable");
  const data=await response.json();
  $("provider").textContent=data.provider==="openai"?"OpenAI-assisted answers":"Local extractive answers";
  $("mode").textContent=data.provider==="openai"?"Selected passages sent to OpenAI":"Extractive mode · no API key";
  const rows=data.documents.map((doc)=>{
    const row=document.createElement("div");row.className="doc";
    const name=document.createElement("strong"),info=document.createElement("span");
    name.textContent=doc.name;info.textContent=doc.chunks+" chunks · version "+doc.version.slice(0,8);
    row.append(name,info);return row;
  });
  if(!rows.length){const p=document.createElement("p");p.className="muted";p.textContent="No documents indexed. Add a sample manual to begin.";rows.push(p);}
  $("documents").replaceChildren(...rows);
}
$("question-form").addEventListener("submit",async(event)=>{
  event.preventDefault();$("ask").disabled=true;$("status").textContent="Searching the document index…";
  try{
    const response=await fetch("/api/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:$("question").value})});
    if(!response.ok)throw Error("The answer service is unavailable. Check the local server and provider settings.");
    const data=await response.json();
    $("answer").textContent=data.answer;$("answer-status").textContent=data.status.replaceAll("_"," ");
    const rows=data.sources.map((source)=>{
      const detail=document.createElement("details");detail.className="source";
      const summary=document.createElement("summary"),text=document.createElement("p"),version=document.createElement("small");
      summary.textContent="["+source.citation_id+"] "+source.name+" · page "+source.page;
      text.textContent=source.text;version.textContent="SHA-256 version: "+source.version;
      detail.append(summary,text,version);return detail;
    });
    $("sources").replaceChildren(...rows);$("answer-panel").hidden=false;
    $("status").textContent=data.status==="answered"?"Answer ready. Inspect supporting passages before relying on it.":"No supported answer was released.";
  }catch(error){$("status").textContent=error.message;}
  finally{$("ask").disabled=false;}
});
$("upload").addEventListener("change",async(event)=>{
  const file=event.target.files[0];if(!file)return;
  if(file.size>200000){$("upload-status").textContent="Choose a TXT or Markdown file under 200 KB.";return;}
  $("upload-status").textContent="Indexing document…";
  try{
    const response=await fetch("/api/documents",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:file.name,text:await file.text()})});
    if(!response.ok)throw Error("Could not index the file. Check its name, extension and contents.");
    $("upload-status").textContent="Document indexed.";await loadDocuments();
  }catch(error){$("upload-status").textContent=error.message;}
  event.target.value="";
});
document.querySelectorAll(".suggestions button").forEach((button)=>button.addEventListener("click",()=>{$("question").value=button.textContent;$("question").focus();}));
loadDocuments().catch((error)=>{$("upload-status").textContent=error.message;});
