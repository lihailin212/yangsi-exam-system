import request from './index'

export const getQuestions = (params) => request.get('/questions', { params })
export const createQuestion = (data) => request.post('/questions', data)
export const updateQuestion = (id, data) => request.put(`/questions/${id}`, data)
export const deleteQuestion = (id) => request.delete(`/questions/${id}`)
export const importQuestions = (formData) => request.post('/questions/import', formData, {
  headers: { 'Content-Type': 'multipart/form-data' }
})

// 分类管理
export const getCategories = () => request.get('/questions/categories')
export const createCategory = (name) =>
  request.post('/questions/categories', { name })
export const renameCategory = (oldName, newName) =>
  request.put('/questions/categories/rename', { old_name: oldName, new_name: newName })
export const deleteCategory = (name) =>
  request.delete(`/questions/categories/${encodeURIComponent(name)}`)

// 随机抽题
export const randomQuestions = (data) => request.post('/questions/random', data)

export const exportQuestions = async (params = {}) => {
  const token = localStorage.getItem('token')
  const query = new URLSearchParams(params).toString()
  const url = `/api/questions/export${query ? '?' + query : ''}`
  
  try {
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    
    if (!response.ok) {
      throw new Error('Export failed')
    }
    
    const blob = await response.blob()
    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = 'questions_export.zip'
    if (contentDisposition) {
      const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
      if (match) {
        filename = match[1].replace(/['"]/g, '')
      }
    }
    
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)
  } catch (error) {
    console.error('Export error:', error)
    throw error
  }
}
