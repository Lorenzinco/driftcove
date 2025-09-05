import { reactive } from 'vue';
export const bus = reactive<{ tick:number } >({ tick:0 });
export function emitRedraw(){ bus.tick++; }