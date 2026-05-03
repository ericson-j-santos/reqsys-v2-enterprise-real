import { reactive } from 'vue'

const toasts = reactive([])
let _id = 0

function add(msg, type = 'info', duration = 4000) {
    const id = ++_id
    toasts.push({ id, msg, type })
    if (duration > 0) setTimeout(() => remove(id), duration)
}

function remove(id) {
    const i = toasts.findIndex(t => t.id === id)
    if (i > -1) toasts.splice(i, 1)
}

export function useToast() {
    return {
        toasts,
        success: (msg) => add(msg, 'success'),
        error: (msg) => add(msg, 'error', 6000),
        warn: (msg) => add(msg, 'warning'),
        info: (msg) => add(msg, 'info'),
        remove,
    }
}
