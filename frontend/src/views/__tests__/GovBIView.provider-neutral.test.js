import { describe, expect, it } from 'vitest'

import source from '../GovBIView.vue?raw'

describe('GovBIView provider-neutral guidance', () => {
  it('directs incident validation to the authorized ReqSys runtime', () => {
    expect(source).toContain('validar a execução autorizada do ReqSys')
    expect(source).not.toContain('ReqSys/Fly')
  })
})
