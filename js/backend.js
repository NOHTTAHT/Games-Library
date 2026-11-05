/* Backend for the Games Library on its own website.
   Supabase holds the data (one table "docs": coll + id + data JSON) and uploaded covers (bucket "covers").
   This file gives the app the same small API it used inside Claude:
     db.collection(name).onSnapshot(cb) / .doc(id).set(data) / .doc(id).delete()
     db.doc("coll/id").onSnapshot(cb) / .set(data)
   Data is loaded once, then kept live with Supabase Realtime. */
(function(){
  "use strict";
  const CFG = window.GL_CONFIG;
  const sb = window.supabase.createClient(CFG.supabaseUrl, CFG.supabaseKey, { auth:{ persistSession:true, autoRefreshToken:true } });

  const cache = {};        // coll -> Map(id -> data)
  const loading = {};      // coll -> Promise
  const subs = {};         // coll -> Set(fn)

  function emit(coll){
    const m = cache[coll]; if(!m) return;
    (subs[coll]||[]).forEach(fn=>{ try{ fn(); }catch(e){ console.error(e); } });
  }
  async function load(coll){
    if(loading[coll]) return loading[coll];
    loading[coll] = (async()=>{
      const m = new Map(); const page = 500;
      for(let from=0;;from+=page){
        const { data, error } = await sb.from("docs").select("id,data").eq("coll", coll).order("id").range(from, from+page-1);
        if(error) throw error;
        data.forEach(r=>m.set(r.id, r.data));
        if(data.length < page) break;
      }
      cache[coll] = m; emit(coll); return m;
    })();
    try{ return await loading[coll]; }catch(e){ delete loading[coll]; throw e; }
  }
  function listen(coll, fn, onErr){
    (subs[coll] = subs[coll] || new Set()).add(fn);
    if(cache[coll]) fn(); else load(coll).catch(e=>{ console.error(e); onErr && onErr(e); });
    return ()=>subs[coll].delete(fn);
  }
  const clone = o => JSON.parse(JSON.stringify(o));
  function docRef(coll, id){
    return {
      id,
      async set(data){
        const d = clone(data);
        const { error } = await sb.from("docs").upsert({ coll, id, data:d, updated_at:new Date().toISOString() });
        if(error){ const e = new Error(error.message); e.code = error.code; throw e; }
        (cache[coll] = cache[coll] || new Map()).set(id, d); emit(coll);
      },
      async delete(){
        const { error } = await sb.from("docs").delete().eq("coll", coll).eq("id", id);
        if(error){ const e = new Error(error.message); e.code = error.code; throw e; }
        if(cache[coll]){ cache[coll].delete(id); emit(coll); }
      },
      onSnapshot(cb, onErr){
        return listen(coll, ()=>{ const m=cache[coll]; const has=m.has(id); cb({ exists:has, id, data:()=>has?clone(m.get(id)):undefined }); }, onErr);
      }
    };
  }
  const db = {
    collection(coll){
      return {
        doc:id=>docRef(coll, id),
        onSnapshot(cb, onErr){
          return listen(coll, ()=>{ const m=cache[coll]; cb({ docs:[...m.entries()].map(([id,d])=>({ id, data:()=>clone(d) })) }); }, onErr);
        }
      };
    },
    doc(path){ const i=path.indexOf("/"); return docRef(path.slice(0,i), path.slice(i+1)); },
    /* Many writes at once (used by the import) */
    async bulkSet(rows, onProgress){
      for(let i=0;i<rows.length;i+=100){
        const chunk = rows.slice(i,i+100).map(r=>({ coll:r.coll, id:r.id, data:clone(r.data), updated_at:new Date().toISOString() }));
        const { error } = await sb.from("docs").upsert(chunk);
        if(error) throw new Error(error.message);
        chunk.forEach(r=>{ (cache[r.coll] = cache[r.coll] || new Map()).set(r.id, r.data); });
        onProgress && onProgress(Math.min(rows.length, i+100), rows.length);
      }
      [...new Set(rows.map(r=>r.coll))].forEach(emit);
    }
  };

  function startRealtime(){
    sb.channel("docs-live").on("postgres_changes", { event:"*", schema:"public", table:"docs" }, p=>{
      const row = p.eventType==="DELETE" ? p.old : p.new; if(!row || !row.coll) return;
      const m = cache[row.coll]; if(!m) return;
      if(p.eventType==="DELETE") m.delete(row.id); else m.set(row.id, row.data);
      emit(row.coll);
    }).subscribe();
  }

  /* Covers: sprite sheets and migrated covers live in this site; new uploads go to Supabase Storage */
  const LOCAL = new Set(CFG.localCovers || []);
  function blobUrl(id){
    id = String(id||"");
    if(id.startsWith("ig:")) return "https://images.igdb.com/igdb/image/upload/t_cover_big/" + encodeURIComponent(id.slice(3)) + ".jpg";
    if(CFG.sheets && CFG.sheets.includes(id)) return "sheets/" + id + ".jpg";
    if(LOCAL.has(id)) return "covers/" + id + ".jpg";
    return CFG.supabaseUrl + "/storage/v1/object/public/covers/" + encodeURIComponent(id);
  }
  const assets = {
    async upload(blob, opts){
      const id = [...crypto.getRandomValues(new Uint8Array(16))].map(b=>b.toString(16).padStart(2,"0")).join("");
      const { error } = await sb.storage.from("covers").upload(id, blob, { contentType:(opts&&opts.type)||blob.type||"image/jpeg", upsert:false });
      if(error){ const e=new Error(error.message); e.code=/size/i.test(error.message)?"too_large":"upload_failed"; throw e; }
      return { id };
    }
  };
  const downloads = {
    async save({ filename, data }){
      const url = URL.createObjectURL(new Blob([data], { type:"application/json" }));
      const a = document.createElement("a"); a.href=url; a.download=filename; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(()=>URL.revokeObjectURL(url), 5000);
    }
  };
  const auth = {
    async session(){ const { data } = await sb.auth.getSession(); return data.session; },
    async signIn(email, password){ const { error } = await sb.auth.signInWithPassword({ email, password }); if(error) throw error; },
    async signOut(){ await sb.auth.signOut(); location.reload(); },
    onChange(fn){ sb.auth.onAuthStateChange((ev, s)=>fn(ev, s)); }
  };

  window.GL_BACKEND = { db, assets, downloads, auth, blobUrl, startRealtime };
})();
