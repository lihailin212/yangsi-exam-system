import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getPublicSettings } from '@/api/settings'

export const useSettingsStore = defineStore('settings', () => {
  const systemName = ref('杨思学考试系统')
  const hospitalName = ref('')
  const logoUrl = ref('')
  const loaded = ref(false)

  async function loadSettings() {
    try {
      const data = await getPublicSettings()
      if (data) {
        systemName.value = data.system_name || '杨思学考试系统'
        hospitalName.value = data.hospital_name || ''
        logoUrl.value = data.logo_url || ''
      }
    } catch (e) {
      console.error('Failed to load settings:', e)
    } finally {
      loaded.value = true
    }
  }

  return { systemName, hospitalName, logoUrl, loaded, loadSettings }
})
