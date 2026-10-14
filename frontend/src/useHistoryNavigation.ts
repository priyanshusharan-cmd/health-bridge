import { useEffect, useState } from "react";

export function useHistoryNavigation() {
  const [availability,setAvailability]=useState({back:false,forward:false});
  useEffect(()=>{
    let position=Number(window.history.state?.healthbridgePosition ?? 0);
    let maximum=position, total=0, last=0, navigating=false, cooldownUntil=0;
    const update=()=>setAvailability({back:position>0,forward:position<maximum});
    const sync=()=>{
      const state=window.history.state;
      if (state?.healthbridgePath === window.location.hash) position=state.healthbridgePosition;
      else {
        position++;maximum=position;
        window.history.replaceState({...state,healthbridgePosition:position,healthbridgePath:window.location.hash},'');
      }
      navigating=false;update();
    };
    window.history.replaceState({...window.history.state,healthbridgePosition:position,healthbridgePath:window.location.hash},'');
    update();
    const wheel=(event:WheelEvent)=>{
      if(event.ctrlKey || event.deltaMode!==0 || Math.abs(event.deltaX)<=Math.abs(event.deltaY)*2 || Math.abs(event.deltaX)<2) return;
      let target=event.target instanceof HTMLElement ? event.target : null;
      // Preserve genuine horizontal scrolling in tabs, text fields and dialogs.
      while(target && target!==document.body) {
        if(target.matches('input,textarea,select,[role="dialog"]')) return;
        if(target.scrollWidth>target.clientWidth && ['auto','scroll'].includes(getComputedStyle(target).overflowX)) return;
        target=target.parentElement;
      }
      if(performance.now()<cooldownUntil) {event.preventDefault();return;}
      const back=event.deltaX<0;
      if(navigating || (back?position<=0:position>=maximum)) return;
      event.preventDefault();
      const now=performance.now();
      if(now-last>250 || Math.sign(total)!==Math.sign(event.deltaX)) total=0;
      total+=event.deltaX;last=now;
      if(Math.abs(total)>=90) {
        navigating=true;total=0;cooldownUntil=performance.now()+650;
        window.history.go(back?-1:1);
      }
    };
    window.addEventListener('hashchange',sync);
    window.addEventListener('popstate',sync);
    window.addEventListener('wheel',wheel,{passive:false});
    return ()=>{
      window.removeEventListener('hashchange',sync);
      window.removeEventListener('popstate',sync);
      window.removeEventListener('wheel',wheel);
    };
  },[]);
  return {back:()=>window.history.back(),forward:()=>window.history.forward(),canBack:availability.back,canForward:availability.forward};
}
