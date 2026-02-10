import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Layout, Input, Button, Card, Steps, Progress, Tag,
  Modal, List, Space, Avatar, Spin, message, Checkbox
} from 'antd'
import {
  SendOutlined, ReloadOutlined, PictureOutlined,
  UnorderedListOutlined, CheckCircleOutlined,
  LoadingOutlined, DeleteOutlined, HomeOutlined,
  EnvironmentOutlined, PhoneOutlined, MailOutlined,
  UserOutlined, CalendarOutlined, InboxOutlined,
  ClockCircleOutlined, MinusCircleOutlined, CloseCircleOutlined,
  CarryOutOutlined, ShoppingOutlined
} from '@ant-design/icons'
import './App.css'

const { Header, Content, Footer } = Layout

// WebSocket 消息类型
const MSG_TYPES = {
  SESSION: 'session',
  TEXT_DELTA: 'text_delta',
  TEXT_DONE: 'text_done',
  METADATA: 'metadata',
  MESSAGE_HISTORY: 'message_history',
  SESSION_RESET: 'session_reset',
  ITEMS_RECOGNIZED: 'items_recognized',
  ITEMS_CONFIRMED: 'items_confirmed',
  ADDRESS_SELECTED: 'address_selected',
  ADDRESS_CONFIRMED: 'address_confirmed',
  TYPING_START: 'typing_start',
  ERROR: 'error'
}

// 阶段配置
const PHASES = [
  { key: 0, title: '开场' },
  { key: 1, title: '人数' },
  { key: 2, title: '地址' },
  { key: 3, title: '日期' },
  { key: 4, title: '物品' },
  { key: 5, title: '其他' },
  { key: 6, title: '确认' }
]

function App() {
  // 基础状态
  const [messages, setMessages] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [isConnected, setIsConnected] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  // 后端状态
  const [currentPhase, setCurrentPhase] = useState(0)
  const [fieldsStatus, setFieldsStatus] = useState({})
  const [quickOptions, setQuickOptions] = useState([])
  const [uiComponent, setUiComponent] = useState({ type: 'none' })
  const [completion, setCompletion] = useState({ completion_rate: 0, can_submit: false })

  // 物品相关
  const [pendingItems, setPendingItems] = useState([])
  const [confirmedItems, setConfirmedItems] = useState([])
  const [isRecognizing, setIsRecognizing] = useState(false)
  const [recognitionStep, setRecognitionStep] = useState(0)
  const [itemsJustConfirmed, setItemsJustConfirmed] = useState(false)  // 刚确认完成，卡片保留显示

  // 地址验证相关
  const [isVerifyingAddress, setIsVerifyingAddress] = useState(false)
  const [addressVerifyStep, setAddressVerifyStep] = useState(0)
  const [pendingAddressData, setPendingAddressData] = useState(null)  // 验证中的地址数据

  // 打字效果队列
  const textQueueRef = useRef([])
  const isTypingRef = useRef(false)

  // 上次的快捷选项（用于避免重复显示）
  const lastOptionsRef = useRef([])

  // 已添加的地址卡片（防止重复）
  const addedAddressCardsRef = useRef({ from: false, to: false })

  // 多选状态（阶段5特殊注意事项）
  const [selectedOptions, setSelectedOptions] = useState([])

  // 弹窗
  const [showPrivacyModal, setShowPrivacyModal] = useState(false)
  const [showItemListModal, setShowItemListModal] = useState(false)

  // 联系方式（登录卡片）
  const [contactPhone, setContactPhone] = useState('')
  const [contactEmail, setContactEmail] = useState('')

  // Refs
  const wsRef = useRef(null)
  const chatEndRef = useRef(null)
  const sessionTokenRef = useRef(localStorage.getItem('erabu_session_token'))

  // 滚动到底部
  const scrollToBottom = useCallback(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  // 打字效果处理
  const processTextQueue = useCallback(() => {
    if (isTypingRef.current || textQueueRef.current.length === 0) return

    isTypingRef.current = true

    const typeNextChar = () => {
      if (textQueueRef.current.length === 0) {
        isTypingRef.current = false
        return
      }

      const char = textQueueRef.current.shift()
      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last?.role === 'assistant' && last?.streaming) {
          return [...prev.slice(0, -1), { ...last, content: last.content + char }]
        }
        return [...prev, { role: 'assistant', content: char, streaming: true }]
      })

      // 根据字符类型调整延迟
      const delay = char === '\n' ? 50 : (char.match(/[，。！？、]/) ? 30 : 15)
      setTimeout(typeNextChar, delay)
    }

    typeNextChar()
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, pendingItems, isRecognizing, scrollToBottom])

  // WebSocket 连接
  useEffect(() => {
    const connect = () => {
      const token = sessionTokenRef.current
      const wsUrl = `ws://localhost:8000/ws/chat${token ? '?session_token=' + token : ''}`
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        setIsConnected(true)
        console.log('WebSocket connected')
      }

      ws.onclose = () => {
        setIsConnected(false)
        console.log('Disconnected, reconnecting...')
        setTimeout(connect, 3000)
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          handleServerMessage(data)
        } catch (e) {
          console.error('Failed to parse message:', e)
        }
      }

      wsRef.current = ws
    }

    connect()
    return () => wsRef.current?.close()
  }, [])

  // 处理服务器消息
  const handleServerMessage = useCallback((data) => {
    console.log('Server message:', data.type, data)

    switch (data.type) {
      case MSG_TYPES.SESSION:
        sessionTokenRef.current = data.session_token
        localStorage.setItem('erabu_session_token', data.session_token)
        if (data.current_phase !== undefined) setCurrentPhase(data.current_phase)
        break

      case MSG_TYPES.TYPING_START:
        // 显示加载状态，表示 Agent 正在处理
        setIsLoading(true)
        break

      case MSG_TYPES.TEXT_DELTA:
        setIsLoading(true)
        // 将内容加入打字队列
        for (const char of data.content) {
          textQueueRef.current.push(char)
        }
        processTextQueue()
        break

      case MSG_TYPES.TEXT_DONE:
        // 等待打字队列处理完成
        const waitForTyping = () => {
          if (textQueueRef.current.length > 0 || isTypingRef.current) {
            setTimeout(waitForTyping, 50)
          } else {
            setIsLoading(false)
            setMessages(prev => {
              const last = prev[prev.length - 1]
              if (last?.streaming) {
                return [...prev.slice(0, -1), { ...last, streaming: false }]
              }
              return prev
            })
          }
        }
        waitForTyping()
        break

      case MSG_TYPES.METADATA:
        if (data.current_phase !== undefined) setCurrentPhase(data.current_phase)
        if (data.fields_status) setFieldsStatus(data.fields_status)
        // 只有当新选项与上次选项不同时才更新（避免重复显示相同选项）
        if (data.quick_options) {
          const newOptions = data.quick_options || []
          const isSame = JSON.stringify(newOptions) === JSON.stringify(lastOptionsRef.current)
          if (!isSame) {
            setQuickOptions(newOptions)
            lastOptionsRef.current = newOptions
          }
        }
        // 处理地址卡片 - 嵌入消息流（带验证动画）
        if (data.ui_component) {
          const uiType = data.ui_component.type
          if (uiType === 'address_confirm' || uiType === 'address_selection') {
            const addressType = data.ui_component.data?.address_type

            // 检查地址是否已确认（从 fields_status 判断）
            const addrField = data.fields_status?.[`${addressType}_address`] || {}
            const isAlreadyConfirmed = addrField.status === 'baseline' && !addrField.needs_confirmation

            // 使用 ref 检查是否已添加过卡片（避免闭包问题导致重复）
            const alreadyAdded = addedAddressCardsRef.current[addressType]

            if (!alreadyAdded && !isAlreadyConfirmed && !isVerifyingAddress) {
              // 标记为正在添加
              addedAddressCardsRef.current[addressType] = true

              // 开始显示验证动画
              setIsVerifyingAddress(true)
              setAddressVerifyStep(0)
              setPendingAddressData({
                type: uiType === 'address_confirm' ? 'address_confirm_card' : 'address_selection_card',
                addressType: addressType,
                data: data.ui_component.data
              })

              // 步骤动画
              let step = 0
              const stepInterval = setInterval(() => {
                step++
                setAddressVerifyStep(step)
                if (step >= 4) {
                  clearInterval(stepInterval)
                  // 动画完成后添加卡片到消息流
                  setTimeout(() => {
                    setMessages(prev => [...prev, {
                      role: 'assistant',
                      type: uiType === 'address_confirm' ? 'address_confirm_card' : 'address_selection_card',
                      addressType: addressType,
                      data: data.ui_component.data,
                      confirmed: false,
                      streaming: false
                    }])
                    setIsVerifyingAddress(false)
                    setPendingAddressData(null)
                  }, 500)
                }
              }, 600)
            } else if (alreadyAdded && isAlreadyConfirmed) {
              // 地址已确认，更新卡片状态
              setMessages(prev => prev.map(msg => {
                if ((msg.type === 'address_confirm_card' || msg.type === 'address_selection_card') &&
                    msg.addressType === addressType) {
                  return { ...msg, confirmed: true }
                }
                return msg
              }))
            }
          }
          setUiComponent(data.ui_component)
        }
        if (data.completion) setCompletion(data.completion)
        break

      case MSG_TYPES.MESSAGE_HISTORY:
        if (data.messages && Array.isArray(data.messages)) {
          setMessages(data.messages.map(m => ({
            role: m.role,
            content: m.content,
            streaming: false
          })))
        }
        break

      case MSG_TYPES.SESSION_RESET:
        sessionTokenRef.current = data.session_token
        localStorage.setItem('erabu_session_token', data.session_token)
        resetState()
        break

      case MSG_TYPES.ITEMS_RECOGNIZED:
        setIsRecognizing(false)
        setPendingItems(data.items || [])
        break

      case MSG_TYPES.ITEMS_CONFIRMED:
        // 服务端确认物品（卡片已在 confirmItems 中嵌入消息流）
        setConfirmedItems(data.items || [])
        break

      case MSG_TYPES.ADDRESS_SELECTED:
        // 服务端确认地址选择
        console.log('Address selected:', data)
        break

      case MSG_TYPES.ADDRESS_CONFIRMED:
        // 服务端确认地址 - 更新嵌入卡片的状态
        console.log('Address confirmed:', data)
        if (data.address_type) {
          setMessages(prev => prev.map(msg => {
            if ((msg.type === 'address_confirm_card' || msg.type === 'address_selection_card') &&
                msg.addressType === data.address_type) {
              return { ...msg, confirmed: true }
            }
            return msg
          }))
        }
        break

      case MSG_TYPES.ERROR:
        message.error(data.message || '发生错误')
        setIsLoading(false)
        break

      default:
        console.log('Unknown message type:', data.type)
    }
  }, [processTextQueue])

  // 重置状态
  const resetState = () => {
    setMessages([])
    setCurrentPhase(0)
    setFieldsStatus({})
    setPendingItems([])
    setConfirmedItems([])
    setQuickOptions([])
    setUiComponent({ type: 'none' })
    setSelectedOptions([])
    setItemsJustConfirmed(false)
    textQueueRef.current = []
    isTypingRef.current = false
    addedAddressCardsRef.current = { from: false, to: false }
  }

  // 发送消息
  const sendMessage = useCallback((content) => {
    if (!content?.trim() || !wsRef.current || !isConnected) return

    // 检查是否是添加物品相关的消息（在物品阶段）
    const addItemKeywords = ['继续添加', '添加物品', '再添加', '上传图片', '还有物品', '还要添加']
    const isAddItemRequest = addItemKeywords.some(kw => content.includes(kw))

    if (isAddItemRequest && currentPhase === 4) {
      // 显示物品识别卡片
      setUiComponent({ type: 'item_evaluation' })
      setQuickOptions([])
      setInputValue('')
      return
    }

    setMessages(prev => [...prev, { role: 'user', content, streaming: false }])
    wsRef.current.send(JSON.stringify({ type: 'message', content }))
    setInputValue('')
    setQuickOptions([]) // 发送消息后清空快捷选项
    lastOptionsRef.current = [] // 重置上次选项记录
    setIsLoading(true)
  }, [isConnected, currentPhase])

  // 处理快捷选项点击
  const handleQuickOption = useCallback((option) => {
    // 检查是否是多选选项（阶段5特殊注意事项）
    const multiSelectOptions = ['有宜家家具', '有钢琴需要搬运', '空调安装', '空调拆卸', '不用品回收']

    // 继续添加物品 - 重新显示物品识别卡片
    if (option === '继续添加' || option === '上传照片') {
      setUiComponent({ type: 'item_evaluation' })
      setQuickOptions([])
      setPendingItems([])  // 清空之前的待确认项
      setItemsJustConfirmed(false)  // 重置确认状态
      return
    }

    if (multiSelectOptions.includes(option)) {
      setSelectedOptions(prev => {
        if (prev.includes(option)) {
          return prev.filter(o => o !== option)
        }
        return [...prev, option]
      })
    } else if (option === '没有了' || option === '没有其他行李' || option === '没有其他行李了') {
      // 如果有已选项，先发送已选项
      if (selectedOptions.length > 0) {
        sendMessage(selectedOptions.join('、'))
        setSelectedOptions([])
      }
      // 清除物品评估卡片状态
      setUiComponent({ type: 'none' })
      sendMessage(option)
    } else {
      sendMessage(option)
    }
  }, [selectedOptions, sendMessage])

  // 确认已选选项
  const confirmSelectedOptions = useCallback(() => {
    if (selectedOptions.length > 0) {
      sendMessage(selectedOptions.join('、'))
      setSelectedOptions([])
    }
  }, [selectedOptions, sendMessage])

  // 重置会话
  const resetSession = useCallback(() => {
    if (wsRef.current && isConnected) {
      wsRef.current.send(JSON.stringify({ type: 'reset_session' }))
    }
  }, [isConnected])

  // 文件选择引用
  const fileInputRef = useRef(null)

  // 上传图片 - 显示隐私协议
  const handleUploadImage = useCallback(() => {
    setShowPrivacyModal(true)
  }, [])

  // 确认隐私协议后打开文件选择器
  const confirmPrivacyAndUpload = useCallback(() => {
    setShowPrivacyModal(false)
    // 触发文件选择
    fileInputRef.current?.click()
  }, [])

  // 处理文件选择后的上传
  const handleFileSelected = useCallback(async (event) => {
    const file = event.target.files?.[0]
    if (!file) return

    // 重置 input 以便可以再次选择同一文件
    event.target.value = ''

    // 验证文件类型
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
    if (!allowedTypes.includes(file.type)) {
      message.error('只支持 JPG、PNG、WebP、GIF 格式的图片')
      return
    }

    // 验证文件大小 (最大 10MB)
    if (file.size > 10 * 1024 * 1024) {
      message.error('图片大小不能超过 10MB')
      return
    }

    setIsRecognizing(true)
    setRecognitionStep(0)

    try {
      // 显示上传进度
      setRecognitionStep(1)

      // 创建 FormData 并上传
      const formData = new FormData()
      formData.append('file', file)
      if (sessionTokenRef.current) {
        formData.append('session_token', sessionTokenRef.current)
      }

      setRecognitionStep(2)

      const response = await fetch('/api/items/upload', {
        method: 'POST',
        body: formData
      })

      setRecognitionStep(3)

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '图片上传失败')
      }

      const result = await response.json()

      setRecognitionStep(4)

      if (!result.success) {
        throw new Error(result.error || '图片识别失败')
      }

      // 转换识别结果格式
      const items = result.items.map((item, index) => ({
        id: index + 1,
        name: item.name,
        name_ja: item.name_ja,
        category: item.category,
        count: item.count || 1,
        confidence: item.confidence,
        note: item.note || ''
      }))

      // 发送识别结果到 WebSocket
      wsRef.current?.send(JSON.stringify({
        type: 'image_uploaded',
        image_id: result.image_id,
        items: items
      }))

      setPendingItems(items)
      message.success(`识别到 ${items.length} 件物品`)

    } catch (error) {
      console.error('Image upload error:', error)
      message.error(error.message || '图片处理失败，请重试')
    } finally {
      setIsRecognizing(false)
    }
  }, [])

  // 确认物品
  const confirmItems = useCallback(() => {
    wsRef.current?.send(JSON.stringify({
      type: 'items_confirmed',
      items: pendingItems
    }))

    // 将卡片作为特殊消息嵌入对话流
    setMessages(prev => [...prev, {
      role: 'assistant',
      type: 'items_card',  // 特殊类型标记
      items: [...pendingItems],
      confirmed: true,
      streaming: false
    }])

    setConfirmedItems(prev => [...prev, ...pendingItems])
    // 清除待确认状态，卡片已嵌入消息流
    setPendingItems([])
    setItemsJustConfirmed(false)
  }, [pendingItems])

  // 删除物品
  const deleteItem = useCallback((id) => {
    setPendingItems(prev => prev.filter(i => i.id !== id))
  }, [])

  // 解析消息内容，支持列表和卡片
  const parseMessageContent = (content) => {
    if (!content) return null

    // 检测是否包含【】标记的卡片内容
    const cardMatch = content.match(/【([^】]+)】([\s\S]*?)(?=\n\n|$)/)

    // 分割内容
    const lines = content.split('\n')
    const elements = []
    let currentList = []
    let inCard = false
    let cardTitle = ''
    let cardContent = []

    lines.forEach((line, i) => {
      // 检测卡片开始
      if (line.match(/^【([^】]+)】/)) {
        if (currentList.length > 0) {
          elements.push(<ul key={`list-${i}`} className="message-list">{currentList}</ul>)
          currentList = []
        }
        inCard = true
        cardTitle = line.match(/^【([^】]+)】/)[1]
        const rest = line.replace(/^【[^】]+】/, '').trim()
        if (rest) cardContent.push(rest)
        return
      }

      // 卡片内容继续
      if (inCard && line.trim() && !line.match(/^[•\-\*]/)) {
        cardContent.push(line)
        return
      }

      // 卡片结束
      if (inCard && (!line.trim() || line.match(/^[•\-\*]/))) {
        elements.push(
          <div key={`card-${i}`} className="message-card">
            <div className="card-title">{cardTitle}</div>
            <div className="card-text">{cardContent.join('\n')}</div>
          </div>
        )
        inCard = false
        cardTitle = ''
        cardContent = []
      }

      // 检测列表项
      if (line.match(/^[•\-\*]\s*/)) {
        const text = line.replace(/^[•\-\*]\s*/, '')
        currentList.push(<li key={`item-${i}`}>{text}</li>)
        return
      }

      // 普通文本
      if (currentList.length > 0) {
        elements.push(<ul key={`list-${i}`} className="message-list">{currentList}</ul>)
        currentList = []
      }

      if (line.trim()) {
        elements.push(<p key={`p-${i}`} className="message-text">{line}</p>)
      } else if (elements.length > 0) {
        elements.push(<div key={`br-${i}`} className="message-break" />)
      }
    })

    // 处理剩余内容
    if (currentList.length > 0) {
      elements.push(<ul key="list-end" className="message-list">{currentList}</ul>)
    }
    if (inCard && cardContent.length > 0) {
      elements.push(
        <div key="card-end" className="message-card">
          <div className="card-title">{cardTitle}</div>
          <div className="card-text">{cardContent.join('\n')}</div>
        </div>
      )
    }

    return elements
  }

  // 渲染消息气泡
  const renderMessage = (msg, index) => {
    // 特殊处理：嵌入式物品卡片
    if (msg.type === 'items_card') {
      return renderEmbeddedItemsCard(msg.items, index)
    }

    // 特殊处理：嵌入式地址确认卡片
    if (msg.type === 'address_confirm_card') {
      return renderEmbeddedAddressConfirmCard(msg, index)
    }

    // 特殊处理：嵌入式地址选择卡片
    if (msg.type === 'address_selection_card') {
      return renderEmbeddedAddressSelectionCard(msg, index)
    }

    return (
      <div key={index} className={`message-wrapper ${msg.role}`}>
        {msg.role === 'assistant' && (
          <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
        )}
        <div className={`message-bubble ${msg.role}`}>
          <div className="message-content">
            {msg.role === 'assistant' ? parseMessageContent(msg.content) : msg.content}
          </div>
          {msg.streaming && <LoadingOutlined style={{ marginLeft: 8 }} />}
        </div>
      </div>
    )
  }

  // 渲染嵌入式物品卡片（已确认，嵌入对话流）
  const renderEmbeddedItemsCard = (items, index) => {
    const groupedItems = items.reduce((acc, item) => {
      const cat = item.category || '其他'
      if (!acc[cat]) acc[cat] = []
      acc[cat].push(item)
      return acc
    }, {})

    const totalCount = items.reduce((sum, i) => sum + (i.count || 1), 0)
    const nonBoxCount = items.filter(i => i.category !== 'ダンボール').length
    const boxItem = items.find(i => i.category === 'ダンボール')

    return (
      <div key={index} className="message-wrapper assistant">
        <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
        <Card className="ui-card recognition-result">
          <div className="result-header">
            <CheckCircleOutlined style={{ color: '#22c55e', fontSize: 20, marginRight: 8 }} />
            <span style={{ color: '#22c55e', fontWeight: 600 }}>识别完成</span>
          </div>
          <p>共新识别出 {nonBoxCount} 件行李物品，另需 {boxItem?.count || 0} 个 L 标准纸箱</p>

          <List
            className="item-list"
            dataSource={Object.entries(groupedItems)}
            renderItem={([category, catItems]) => (
              <div key={category}>
                <div className="item-category">{category}</div>
                {catItems.map(item => (
                  <div key={item.id} className="item-row">
                    <div className="item-info">
                      <span className="item-name">{item.name_ja || item.name}</span>
                      {item.note && <span className="item-note">{item.note}</span>}
                    </div>
                    <Tag color="blue">×{item.count || 1}</Tag>
                  </div>
                ))}
              </div>
            )}
          />

          <Button type="primary" block disabled style={{ marginTop: 16, backgroundColor: '#52c41a', borderColor: '#52c41a' }}>
            <CheckCircleOutlined /> 已添加（{totalCount}件）
          </Button>
          <p className="hint">添加后您可以继续拍照/从目录中添加行李</p>
        </Card>
      </div>
    )
  }

  // 渲染嵌入式地址确认卡片
  const renderEmbeddedAddressConfirmCard = (msg, index) => {
    const data = msg.data || {}
    const addressType = msg.addressType || 'from'
    const addressLabel = addressType === 'from' ? '搬出' : '搬入'

    // 检查地址是否已确认（通过 fieldsStatus 判断）
    const addressField = fieldsStatus[`${addressType}_address`] || {}
    const isConfirmed = msg.confirmed || (addressField.status === 'baseline' && !addressField.needs_confirmation)

    return (
      <div key={index} className="message-wrapper assistant">
        <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
        <Card className="ui-card address-confirm-card">
          <div className="card-body">
            {isConfirmed ? (
              <>
                <div className="result-header" style={{ marginBottom: 12 }}>
                  <CheckCircleOutlined style={{ color: '#22c55e', fontSize: 20, marginRight: 8 }} />
                  <span style={{ color: '#22c55e', fontWeight: 600 }}>{addressLabel}地址已确认</span>
                </div>
              </>
            ) : (
              <>
                <h3><EnvironmentOutlined style={{ marginRight: 8 }} />确认{addressLabel}地址</h3>
                <p style={{ color: '#666', marginBottom: 16 }}>{data.message || '请确认以下地址是否正确'}</p>
              </>
            )}

            <div style={{
              padding: '16px',
              background: '#f9fafb',
              borderRadius: 8,
              border: '1px solid #e5e7eb',
              marginBottom: 16
            }}>
              <div style={{ fontWeight: 500, fontSize: 16, marginBottom: 8 }}>
                {data.formatted_address}
              </div>
              <div style={{ fontSize: 13, color: '#666' }}>
                {data.postal_code && (
                  <div style={{ marginBottom: 4 }}>
                    <Tag color="blue">〒{data.postal_code}</Tag>
                  </div>
                )}
                <div>
                  {data.prefecture && <span>{data.prefecture}</span>}
                  {data.city && <span> {data.city}</span>}
                  {data.district && <span> {data.district}</span>}
                </div>
              </div>
            </div>

            {isConfirmed ? (
              <Button type="primary" block disabled style={{ backgroundColor: '#52c41a', borderColor: '#52c41a' }}>
                <CheckCircleOutlined /> 已确认
              </Button>
            ) : (
              <Space style={{ width: '100%' }} direction="vertical">
                <Button
                  type="primary"
                  block
                  size="large"
                  icon={<CheckCircleOutlined />}
                  onClick={() => handleAddressConfirmed(addressType, true)}
                >
                  确认正确
                </Button>
                <Button
                  block
                  onClick={() => handleAddressConfirmed(addressType, false)}
                >
                  不对，重新输入
                </Button>
              </Space>
            )}
          </div>
        </Card>
      </div>
    )
  }

  // 渲染嵌入式地址选择卡片
  const renderEmbeddedAddressSelectionCard = (msg, index) => {
    const data = msg.data || {}
    const addressType = msg.addressType || 'from'
    const candidates = data.candidates || []
    const originalInput = data.original_input || ''
    const addressLabel = addressType === 'from' ? '搬出' : '搬入'

    // 检查是否已选择
    const addressField = fieldsStatus[`${addressType}_address`] || {}
    const isSelected = msg.confirmed || addressField.verification_status === 'verified'

    return (
      <div key={index} className="message-wrapper assistant">
        <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
        <Card className="ui-card address-selection-card">
          <div className="card-body">
            {isSelected ? (
              <div className="result-header" style={{ marginBottom: 12 }}>
                <CheckCircleOutlined style={{ color: '#22c55e', fontSize: 20, marginRight: 8 }} />
                <span style={{ color: '#22c55e', fontWeight: 600 }}>已选择{addressLabel}地址</span>
              </div>
            ) : (
              <>
                <h3><EnvironmentOutlined style={{ marginRight: 8 }} />选择{addressLabel}地址</h3>
                <p style={{ color: '#666', marginBottom: 16 }}>
                  找到多个匹配地址，请选择正确的一个
                </p>
                <p style={{ fontSize: 12, color: '#999', marginBottom: 12 }}>
                  您输入的：{originalInput}
                </p>
              </>
            )}

            {!isSelected && (
              <>
                <List
                  className="address-candidate-list"
                  dataSource={candidates}
                  renderItem={(addr, idx) => (
                    <div
                      key={idx}
                      className="address-candidate-item"
                      style={{
                        padding: '12px',
                        marginBottom: 8,
                        background: '#f9fafb',
                        borderRadius: 8,
                        border: '1px solid #e5e7eb',
                        cursor: 'pointer',
                        transition: 'all 0.2s'
                      }}
                      onClick={() => handleAddressSelected(addressType, addr)}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = '#f0f5ff'
                        e.currentTarget.style.borderColor = '#6366f1'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = '#f9fafb'
                        e.currentTarget.style.borderColor = '#e5e7eb'
                      }}
                    >
                      <div style={{ fontWeight: 500, marginBottom: 4 }}>
                        {addr.formatted_address}
                      </div>
                      <div style={{ fontSize: 12, color: '#666' }}>
                        {addr.postal_code && <Tag color="blue">〒{addr.postal_code}</Tag>}
                        {addr.prefecture && <span style={{ marginRight: 8 }}>{addr.prefecture}</span>}
                        {addr.city && <span>{addr.city}</span>}
                        {addr.district && <span>{addr.district}</span>}
                      </div>
                    </div>
                  )}
                />

                <Button
                  block
                  style={{ marginTop: 12 }}
                  onClick={() => sendMessage('以上都不对，重新输入')}
                >
                  以上都不对，重新输入
                </Button>
              </>
            )}

            {isSelected && (
              <Button type="primary" block disabled style={{ backgroundColor: '#52c41a', borderColor: '#52c41a' }}>
                <CheckCircleOutlined /> 已选择
              </Button>
            )}
          </div>
        </Card>
      </div>
    )
  }

  // 渲染物品评估卡片
  const renderItemEvalCard = () => (
    <Card className="ui-card item-eval-card">
      <div className="card-image">
        <PictureOutlined style={{ fontSize: 48, color: '#9ca3af' }} />
        <span>示意图</span>
      </div>
      <div className="card-body">
        <h3>智能物品识别</h3>
        <p>通过我们的AI识别您的家具照片以加快报价流程，或从我们的目录中手动选择物品。</p>
        <Button type="primary" icon={<PictureOutlined />} block onClick={handleUploadImage}>
          上传图片
        </Button>
        <Button icon={<UnorderedListOutlined />} block style={{ marginTop: 8 }} onClick={() => sendMessage('从目录中选择')}>
          从目录中选择
        </Button>
      </div>
    </Card>
  )

  // 渲染识别进度
  const renderRecognitionProgress = () => (
    <Card className="ui-card recognition-card">
      <p style={{ marginBottom: 16 }}>收到🎉，接下来识别您图片中的行李</p>
      <Steps
        direction="vertical"
        size="small"
        current={recognitionStep}
        items={[
          { title: '隐私处理' },
          { title: '行李识别' },
          { title: '统计包装小件物品纸箱数量' },
          { title: '整合结果' }
        ]}
      />
    </Card>
  )

  // 渲染地址验证进度
  const renderAddressVerifyProgress = () => {
    const addressLabel = pendingAddressData?.addressType === 'from' ? '搬出' : '搬入'
    return (
      <Card className="ui-card address-verify-progress-card">
        <p style={{ marginBottom: 16 }}>收到🎉，接下来我将解析并验证地址准确性</p>
        <Steps
          direction="vertical"
          size="small"
          current={addressVerifyStep}
          items={[
            { title: '解析地址' },
            { title: '查询地址', description: <Tag color="blue">Google Map</Tag> },
            { title: '验证地址准确性、完整性、唯一性' },
            { title: '整合查询结果' }
          ]}
        />
      </Card>
    )
  }

  // 渲染识别结果
  const renderRecognitionResult = () => {
    const groupedItems = pendingItems.reduce((acc, item) => {
      const cat = item.category || '其他'
      if (!acc[cat]) acc[cat] = []
      acc[cat].push(item)
      return acc
    }, {})

    const totalCount = pendingItems.reduce((sum, i) => sum + (i.count || 1), 0)
    const nonBoxCount = pendingItems.filter(i => i.category !== 'ダンボール').length
    const boxItem = pendingItems.find(i => i.category === 'ダンボール')

    return (
      <Card className="ui-card recognition-result">
        <div className="result-header">
          <CheckCircleOutlined style={{ color: '#22c55e', fontSize: 20, marginRight: 8 }} />
          <span style={{ color: '#22c55e', fontWeight: 600 }}>识别完成</span>
        </div>
        <p>共新识别出 {nonBoxCount} 件行李物品，另需 {boxItem?.count || 0} 个 L 标准纸箱</p>

        <List
          className="item-list"
          dataSource={Object.entries(groupedItems)}
          renderItem={([category, items]) => (
            <div key={category}>
              <div className="item-category">{category}</div>
              {items.map(item => (
                <div key={item.id} className="item-row">
                  <div className="item-info">
                    <span className="item-name">{item.name_ja || item.name}</span>
                    {item.note && <span className="item-note">{item.note}</span>}
                  </div>
                  <Space>
                    <Tag color="blue">×{item.count || 1}</Tag>
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => deleteItem(item.id)}
                    />
                  </Space>
                </div>
              ))}
            </div>
          )}
        />

        <Button type="primary" block onClick={confirmItems} style={{ marginTop: 16 }}>
          确认添加（{totalCount}件）
        </Button>
        <p className="hint">添加后您可以继续拍照/从目录中添加行李</p>
      </Card>
    )
  }

  // 处理地址选择（从多个候选中选择）
  const handleAddressSelected = useCallback((addressType, selectedAddress) => {
    wsRef.current?.send(JSON.stringify({
      type: 'address_selected',
      address_type: addressType,
      address: selectedAddress
    }))

    // 立即更新嵌入卡片的状态
    setMessages(prev => prev.map(msg => {
      if (msg.type === 'address_selection_card' && msg.addressType === addressType) {
        return { ...msg, confirmed: true }
      }
      return msg
    }))
  }, [])

  // 处理地址确认
  const handleAddressConfirmed = useCallback((addressType, confirmed) => {
    // 立即显示加载状态
    setIsLoading(true)

    wsRef.current?.send(JSON.stringify({
      type: 'address_confirmed',
      address_type: addressType,
      confirmed: confirmed
    }))

    // 立即更新嵌入卡片的状态
    if (confirmed) {
      setMessages(prev => prev.map(msg => {
        if (msg.type === 'address_confirm_card' && msg.addressType === addressType) {
          return { ...msg, confirmed: true }
        }
        return msg
      }))
    }
  }, [])

  // 渲染地址选择卡片（多候选地址）
  const renderAddressSelectionCard = () => {
    const data = uiComponent.data || {}
    const addressType = data.address_type || 'from'
    const candidates = data.candidates || []
    const originalInput = data.original_input || ''
    const addressLabel = addressType === 'from' ? '搬出' : '搬入'

    return (
      <Card className="ui-card address-selection-card">
        <div className="card-body">
          <h3><EnvironmentOutlined style={{ marginRight: 8 }} />选择{addressLabel}地址</h3>
          <p style={{ color: '#666', marginBottom: 16 }}>
            找到多个匹配地址，请选择正确的一个
          </p>
          <p style={{ fontSize: 12, color: '#999', marginBottom: 12 }}>
            您输入的：{originalInput}
          </p>

          <List
            className="address-candidate-list"
            dataSource={candidates}
            renderItem={(addr, index) => (
              <div
                key={index}
                className="address-candidate-item"
                style={{
                  padding: '12px',
                  marginBottom: 8,
                  background: '#f9fafb',
                  borderRadius: 8,
                  border: '1px solid #e5e7eb',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                onClick={() => handleAddressSelected(addressType, addr)}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#f0f5ff'
                  e.currentTarget.style.borderColor = '#6366f1'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = '#f9fafb'
                  e.currentTarget.style.borderColor = '#e5e7eb'
                }}
              >
                <div style={{ fontWeight: 500, marginBottom: 4 }}>
                  {addr.formatted_address}
                </div>
                <div style={{ fontSize: 12, color: '#666' }}>
                  {addr.postal_code && <Tag color="blue">〒{addr.postal_code}</Tag>}
                  {addr.prefecture && <span style={{ marginRight: 8 }}>{addr.prefecture}</span>}
                  {addr.city && <span>{addr.city}</span>}
                  {addr.district && <span>{addr.district}</span>}
                </div>
              </div>
            )}
          />

          <Button
            block
            style={{ marginTop: 12 }}
            onClick={() => sendMessage('以上都不对，重新输入')}
          >
            以上都不对，重新输入
          </Button>
        </div>
      </Card>
    )
  }

  // 渲染地址确认卡片（单地址确认）
  const renderAddressConfirmCard = () => {
    const data = uiComponent.data || {}
    const addressType = data.address_type || 'from'
    const addressLabel = addressType === 'from' ? '搬出' : '搬入'

    return (
      <Card className="ui-card address-confirm-card">
        <div className="card-body">
          <h3><EnvironmentOutlined style={{ marginRight: 8 }} />确认{addressLabel}地址</h3>
          <p style={{ color: '#666', marginBottom: 16 }}>{data.message || '请确认以下地址是否正确'}</p>

          <div style={{
            padding: '16px',
            background: '#f9fafb',
            borderRadius: 8,
            border: '1px solid #e5e7eb',
            marginBottom: 16
          }}>
            <div style={{ fontWeight: 500, fontSize: 16, marginBottom: 8 }}>
              {data.formatted_address}
            </div>
            <div style={{ fontSize: 13, color: '#666' }}>
              {data.postal_code && (
                <div style={{ marginBottom: 4 }}>
                  <Tag color="blue">〒{data.postal_code}</Tag>
                </div>
              )}
              <div>
                {data.prefecture && <span>{data.prefecture}</span>}
                {data.city && <span> {data.city}</span>}
                {data.district && <span> {data.district}</span>}
              </div>
            </div>
          </div>

          <Space style={{ width: '100%' }} direction="vertical">
            <Button
              type="primary"
              block
              size="large"
              icon={<CheckCircleOutlined />}
              onClick={() => handleAddressConfirmed(addressType, true)}
            >
              确认正确
            </Button>
            <Button
              block
              onClick={() => handleAddressConfirmed(addressType, false)}
            >
              不对，重新输入
            </Button>
          </Space>
        </div>
      </Card>
    )
  }

  // 渲染地址验证卡片（旧版兼容）
  const renderAddressVerifyCard = () => {
    const data = uiComponent.data || {}
    const fromAddr = data.from_address || {}
    const toAddr = data.to_address || {}

    return (
      <Card className="ui-card address-verify-card">
        <div className="card-body">
          <h3><EnvironmentOutlined style={{ marginRight: 8 }} />地址确认</h3>
          <p>请确认以下地址信息是否正确</p>

          {fromAddr.value && (
            <div style={{ marginBottom: 16 }}>
              <Tag color="orange">搬出地址</Tag>
              <p style={{ marginTop: 8, padding: '12px', background: '#f5f5f5', borderRadius: 8 }}>
                {fromAddr.value}
              </p>
              <Space style={{ marginTop: 8 }}>
                <Button type="primary" onClick={() => sendMessage('搬出地址正确')}>
                  地址正确
                </Button>
                <Button onClick={() => sendMessage('修改搬出地址')}>
                  需要修改
                </Button>
              </Space>
            </div>
          )}

          {toAddr.value && (
            <div>
              <Tag color="green">搬入地址</Tag>
              <p style={{ marginTop: 8, padding: '12px', background: '#f5f5f5', borderRadius: 8 }}>
                {toAddr.value}
              </p>
              <Space style={{ marginTop: 8 }}>
                <Button type="primary" onClick={() => sendMessage('搬入地址正确')}>
                  地址正确
                </Button>
                <Button onClick={() => sendMessage('修改搬入地址')}>
                  需要修改
                </Button>
              </Space>
            </div>
          )}
        </div>
      </Card>
    )
  }

  // 渲染确认卡片
  const renderConfirmCard = () => {
    const data = uiComponent.data || {}
    const fields = data.fields_status || fieldsStatus

    const getFieldDisplay = (field, defaultValue = '未设置') => {
      if (!field) return defaultValue
      if (typeof field === 'object') {
        return field.value || field.display || defaultValue
      }
      return field
    }

    return (
      <Card className="ui-card confirm-card">
        <div className="card-body">
          <div style={{ textAlign: 'center', marginBottom: 16 }}>
            <CheckCircleOutlined style={{ fontSize: 48, color: '#22c55e' }} />
            <h3 style={{ marginTop: 8 }}>信息确认</h3>
            <p>请确认以下搬家信息是否正确</p>
          </div>

          <List
            itemLayout="horizontal"
            dataSource={[
              { label: '搬家人数', value: getFieldDisplay(fields.people_count), icon: <UserOutlined /> },
              { label: '搬出地址', value: getFieldDisplay(fields.from_address), icon: <EnvironmentOutlined /> },
              { label: '搬入地址', value: getFieldDisplay(fields.to_address), icon: <EnvironmentOutlined /> },
              { label: '搬家日期', value: getFieldDisplay(fields.moving_date), icon: <CalendarOutlined /> },
              { label: '物品数量', value: fields.items?.list ? `${fields.items.list.length}件` : '未设置', icon: <InboxOutlined /> }
            ]}
            renderItem={item => (
              <List.Item>
                <List.Item.Meta
                  avatar={item.icon}
                  title={item.label}
                  description={item.value}
                />
              </List.Item>
            )}
          />

          <div style={{ marginTop: 16 }}>
            <Button type="primary" block size="large" onClick={() => sendMessage('确认无误，提交报价')}>
              确认并提交报价
            </Button>
            <Button block style={{ marginTop: 8 }} onClick={() => sendMessage('我要修改信息')}>
              修改信息
            </Button>
          </div>
        </div>
      </Card>
    )
  }

  // 渲染登录卡片
  const renderLoginCard = () => {
    const handleSubmitContact = () => {
      if (contactPhone || contactEmail) {
        wsRef.current?.send(JSON.stringify({
          type: 'submit_quote',
          phone: contactPhone,
          email: contactEmail
        }))
        setContactPhone('')
        setContactEmail('')
      } else {
        message.warning('请输入手机号或邮箱')
      }
    }

    return (
      <Card className="ui-card login-card">
        <div className="card-body">
          <div style={{ textAlign: 'center', marginBottom: 16 }}>
            <UserOutlined style={{ fontSize: 48, color: '#6366f1' }} />
            <h3 style={{ marginTop: 8 }}>获取报价</h3>
            <p>请留下联系方式，我们会尽快为您联系搬家公司</p>
          </div>

          <Input
            prefix={<PhoneOutlined />}
            placeholder="手机号码"
            value={contactPhone}
            onChange={(e) => setContactPhone(e.target.value)}
            style={{ marginBottom: 12 }}
            size="large"
          />

          <Input
            prefix={<MailOutlined />}
            placeholder="邮箱地址（选填）"
            value={contactEmail}
            onChange={(e) => setContactEmail(e.target.value)}
            style={{ marginBottom: 16 }}
            size="large"
          />

          <Button type="primary" block size="large" onClick={handleSubmitContact}>
            提交并获取报价
          </Button>

          <p style={{ textAlign: 'center', fontSize: 12, color: '#999', marginTop: 12 }}>
            提交后，我们会为您匹配合适的搬家公司
          </p>
        </div>
      </Card>
    )
  }

  // 渲染快捷选项
  const renderQuickOptions = () => {
    if (!quickOptions.length) return null

    const multiSelectOptions = ['有宜家家具', '有钢琴需要搬运', '空调安装', '空调拆卸', '不用品回收']

    return (
      <div className="quick-options">
        {quickOptions.map((opt, i) => {
          const isMultiSelect = multiSelectOptions.includes(opt)
          const isSelected = selectedOptions.includes(opt)

          return (
            <Button
              key={i}
              className={`quick-option ${isSelected ? 'selected' : ''}`}
              onClick={() => handleQuickOption(opt)}
            >
              {isMultiSelect && <Checkbox checked={isSelected} style={{ marginRight: 4 }} />}
              {opt}
            </Button>
          )
        })}

        {selectedOptions.length > 0 && (
          <Button type="primary" onClick={confirmSelectedOptions}>
            确认选择 ({selectedOptions.length})
          </Button>
        )}
      </div>
    )
  }

  return (
    <Layout className="app-layout">
      {/* 隐藏的文件选择器 */}
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        accept="image/jpeg,image/png,image/webp,image/gif"
        onChange={handleFileSelected}
      />

      {/* Header */}
      <Header className="app-header">
        <div className="header-left">
          <HomeOutlined style={{ fontSize: 20, marginRight: 8 }} />
          <span className="header-title">ERABU</span>
        </div>
        <Button type="link" onClick={() => setShowItemListModal(true)}>
          搬家清单
        </Button>
      </Header>

      {/* Progress */}
      <div className="progress-section">
        <div className="segmented-progress">
          {PHASES.map((p, i) => (
            <div
              key={i}
              className={`progress-segment ${i < currentPhase ? 'completed' : i === currentPhase ? 'active' : 'pending'}`}
            />
          ))}
        </div>
      </div>

      {/* Chat Area */}
      <Content className="chat-area">
        {messages.map(renderMessage)}

        {/* UI Components based on backend */}
        {uiComponent.type === 'item_evaluation' && !isRecognizing && !pendingItems.length && (
          <div className="message-wrapper assistant">
            <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
            {renderItemEvalCard()}
          </div>
        )}

        {uiComponent.type === 'address_verify' && (
          <div className="message-wrapper assistant">
            <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
            {renderAddressVerifyCard()}
          </div>
        )}

        {/* 地址选择和确认卡片已嵌入消息流，不再在此独立渲染 */}

        {uiComponent.type === 'confirm_card' && (
          <div className="message-wrapper assistant">
            <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
            {renderConfirmCard()}
          </div>
        )}

        {uiComponent.type === 'login_card' && (
          <div className="message-wrapper assistant">
            <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
            {renderLoginCard()}
          </div>
        )}

        {isRecognizing && (
          <div className="message-wrapper assistant">
            <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
            {renderRecognitionProgress()}
          </div>
        )}

        {/* 地址验证进度 */}
        {isVerifyingAddress && (
          <div className="message-wrapper assistant">
            <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
            {renderAddressVerifyProgress()}
          </div>
        )}

        {/* 待确认的物品卡片（确认后会嵌入消息流，这里只显示未确认的） */}
        {pendingItems.length > 0 && !isRecognizing && (
          <div className="message-wrapper assistant">
            <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
            {renderRecognitionResult()}
          </div>
        )}

        {/* 显示加载状态：当 isLoading 为 true 且最后一条消息不在流式输出中 */}
        {isLoading && !messages[messages.length - 1]?.streaming && (
          <div className="message-wrapper assistant">
            <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
            <Spin indicator={<LoadingOutlined />} />
          </div>
        )}

        {/* Quick Options - 在聊天流中 (物品识别或地址验证进行中时不显示) */}
        {!pendingItems.length && !isRecognizing && !isVerifyingAddress && renderQuickOptions()}

        <div ref={chatEndRef} />
      </Content>

      {/* Input */}
      <Footer className="input-footer">
        <Input
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onPressEnter={() => sendMessage(inputValue)}
          placeholder="问我问题或输入消息..."
          suffix={
            <Button
              type="primary"
              shape="circle"
              icon={<SendOutlined />}
              onClick={() => sendMessage(inputValue)}
              disabled={!isConnected || !inputValue.trim()}
            />
          }
        />
        <Button
          icon={<ReloadOutlined />}
          onClick={resetSession}
          style={{ marginLeft: 8 }}
        >
          重置
        </Button>
      </Footer>

      {/* Phase Indicator */}
      <div className="phase-indicator">
        {isConnected ? '已连接' : '连接中...'} | {PHASES[currentPhase]?.title || '开场'}
      </div>

      {/* Privacy Modal */}
      <Modal
        title="💡 温馨提示"
        open={showPrivacyModal}
        onOk={confirmPrivacyAndUpload}
        onCancel={() => setShowPrivacyModal(false)}
        okText="我知道了"
        cancelText="取消"
      >
        <p>上传的照片仅用于识别物品，不会保存或用于其他用途。</p>
        <p>识别完成后会自动删除。</p>
      </Modal>

      {/* Item List Modal - 搬家清单 */}
      <Modal
        title="搬家清单"
        open={showItemListModal}
        onCancel={() => setShowItemListModal(false)}
        footer={null}
        width={420}
      >
        <div className="checklist-modal">
          {/* 所有字段状态列表 */}
          {(() => {
            // 定义所有需要收集的字段
            const allFields = [
              // 阶段1: 人数
              {
                key: 'people_count',
                label: '搬家人数',
                phase: 1,
                icon: <UserOutlined />,
                getStatus: () => fieldsStatus.people_count_status || 'not_collected',
                getValue: () => {
                  const v = fieldsStatus.people_count
                  return v ? `${v}人` : null
                }
              },
              // 阶段2: 地址
              {
                key: 'from_address',
                label: '搬出地址',
                phase: 2,
                icon: <EnvironmentOutlined />,
                getStatus: () => fieldsStatus.from_address?.status || 'not_collected',
                getValue: () => {
                  const addr = fieldsStatus.from_address
                  if (!addr?.value) return null
                  let display = addr.value
                  if (addr.postal_code) display = `〒${addr.postal_code} ${display}`
                  return display
                }
              },
              {
                key: 'from_building_type',
                label: '搬出建筑类型',
                phase: 2,
                icon: <HomeOutlined />,
                getStatus: () => fieldsStatus.from_address?.building_type ? 'baseline' : 'not_collected',
                getValue: () => fieldsStatus.from_address?.building_type || null
              },
              {
                key: 'from_room_type',
                label: '搬出户型',
                phase: 2,
                icon: <HomeOutlined />,
                getStatus: () => fieldsStatus.from_address?.room_type ? 'baseline' : 'not_collected',
                getValue: () => fieldsStatus.from_address?.room_type || null,
                // 只有公寓类建筑才需要户型
                isVisible: () => {
                  const bt = fieldsStatus.from_address?.building_type
                  return bt && ['マンション', 'アパート', 'タワーマンション', '団地', 'ビル'].includes(bt)
                }
              },
              {
                key: 'to_address',
                label: '搬入地址',
                phase: 2,
                icon: <EnvironmentOutlined />,
                getStatus: () => fieldsStatus.to_address?.status || 'not_collected',
                getValue: () => {
                  const addr = fieldsStatus.to_address
                  if (!addr?.value && !addr?.city) return null
                  return addr.value || addr.city || null
                }
              },
              // 阶段3: 日期
              {
                key: 'move_date',
                label: '搬家日期',
                phase: 3,
                icon: <CalendarOutlined />,
                getStatus: () => fieldsStatus.move_date?.status || 'not_collected',
                getValue: () => {
                  const date = fieldsStatus.move_date
                  if (!date?.value && !date?.month) return null
                  let display = date.value || ''
                  if (!display && date.month) {
                    display = `${date.year || new Date().getFullYear()}年${date.month}月`
                    if (date.day) display += `${date.day}日`
                    else if (date.period) display += `${date.period}`
                  }
                  if (date.time_slot) display += ` ${date.time_slot}`
                  return display || null
                }
              },
              // 阶段4: 物品
              {
                key: 'items',
                label: '物品清单',
                phase: 4,
                icon: <ShoppingOutlined />,
                getStatus: () => {
                  const items = fieldsStatus.items
                  if (!items) return 'not_collected'
                  if (items.status === 'baseline' || items.status === 'ideal') return 'baseline'
                  if (items.status === 'in_progress') return 'in_progress'
                  if (items.status === 'asked') return 'asked'
                  if (items.list?.length > 0) return 'in_progress'
                  return 'not_collected'
                },
                getValue: () => {
                  const items = fieldsStatus.items?.list || confirmedItems
                  if (!items || items.length === 0) return null
                  const count = items.reduce((sum, item) => sum + (item.count || 1), 0)
                  return `${items.length}种 共${count}件`
                }
              },
              // 阶段5: 其他信息
              {
                key: 'from_floor_elevator',
                label: '搬出楼层电梯',
                phase: 5,
                icon: <HomeOutlined />,
                getStatus: () => fieldsStatus.from_floor_elevator?.status || 'not_collected',
                getValue: () => {
                  const floor = fieldsStatus.from_floor_elevator
                  if (!floor) return null
                  let parts = []
                  if (floor.floor) parts.push(`${floor.floor}楼`)
                  if (floor.has_elevator === true) parts.push('有电梯')
                  else if (floor.has_elevator === false) parts.push('无电梯')
                  return parts.length > 0 ? parts.join(' ') : null
                },
                // 只有公寓类建筑才需要
                isVisible: () => {
                  const bt = fieldsStatus.from_address?.building_type
                  return bt && ['マンション', 'アパート', 'タワーマンション', '団地', 'ビル'].includes(bt)
                }
              },
              {
                key: 'to_floor_elevator',
                label: '搬入楼层电梯',
                phase: 5,
                icon: <HomeOutlined />,
                getStatus: () => fieldsStatus.to_floor_elevator?.status || 'not_collected',
                getValue: () => {
                  const floor = fieldsStatus.to_floor_elevator
                  if (!floor) return null
                  let parts = []
                  if (floor.floor) parts.push(`${floor.floor}楼`)
                  if (floor.has_elevator === true) parts.push('有电梯')
                  else if (floor.has_elevator === false) parts.push('无电梯')
                  else if (floor.has_elevator === '还不清楚') parts.push('待定')
                  return parts.length > 0 ? parts.join(' ') : null
                }
              },
              {
                key: 'packing_service',
                label: '打包服务',
                phase: 5,
                icon: <InboxOutlined />,
                getStatus: () => fieldsStatus.packing_service_status || (fieldsStatus.packing_service ? 'baseline' : 'not_collected'),
                getValue: () => fieldsStatus.packing_service || null
              },
              {
                key: 'special_notes',
                label: '特殊注意事项',
                phase: 5,
                icon: <CarryOutOutlined />,
                getStatus: () => {
                  if (fieldsStatus.special_notes_done) return 'baseline'
                  if (fieldsStatus.special_notes?.length > 0) return 'in_progress'
                  if (fieldsStatus.special_notes_status === 'asked') return 'asked'
                  return fieldsStatus.special_notes_status || 'not_collected'
                },
                getValue: () => {
                  if (fieldsStatus.special_notes_done && (!fieldsStatus.special_notes || fieldsStatus.special_notes.length === 0)) {
                    return '无'
                  }
                  return fieldsStatus.special_notes?.length > 0 ? fieldsStatus.special_notes.join('、') : null
                }
              },
            ]

            // 状态图标和颜色映射
            const getStatusDisplay = (status, value) => {
              switch (status) {
                case 'baseline':
                case 'ideal':
                  return { icon: <CheckCircleOutlined />, color: '#52c41a', text: '已收集' }
                case 'asked':
                  return { icon: <ClockCircleOutlined />, color: '#faad14', text: '待回答' }
                case 'in_progress':
                  return { icon: <LoadingOutlined />, color: '#1890ff', text: '收集中' }
                case 'skipped':
                  return { icon: <CloseCircleOutlined />, color: '#ff4d4f', text: '已跳过' }
                default:
                  return { icon: <MinusCircleOutlined />, color: '#d9d9d9', text: '未收集' }
              }
            }

            // 按阶段分组
            const phaseGroups = {
              1: { title: '阶段1: 人数', fields: [] },
              2: { title: '阶段2: 地址', fields: [] },
              3: { title: '阶段3: 日期', fields: [] },
              4: { title: '阶段4: 物品', fields: [] },
              5: { title: '阶段5: 其他信息', fields: [] },
            }

            allFields.forEach(field => {
              // 检查字段是否应该显示
              if (field.isVisible && !field.isVisible()) return
              phaseGroups[field.phase].fields.push(field)
            })

            return (
              <>
                {Object.entries(phaseGroups).map(([phase, group]) => (
                  group.fields.length > 0 && (
                    <div key={phase} className="checklist-phase-group" style={{ marginBottom: 16 }}>
                      <div style={{
                        fontSize: 12,
                        color: '#666',
                        marginBottom: 8,
                        paddingBottom: 4,
                        borderBottom: '1px solid #f0f0f0'
                      }}>
                        {group.title}
                      </div>
                      {group.fields.map(field => {
                        const status = field.getStatus()
                        const value = field.getValue()
                        const statusDisplay = getStatusDisplay(status, value)

                        return (
                          <div
                            key={field.key}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              padding: '8px 0',
                              borderBottom: '1px solid #fafafa'
                            }}
                          >
                            {/* 状态图标 */}
                            <span style={{
                              color: statusDisplay.color,
                              fontSize: 16,
                              marginRight: 8,
                              width: 20,
                              textAlign: 'center'
                            }}>
                              {statusDisplay.icon}
                            </span>

                            {/* 字段图标 */}
                            <span style={{ color: '#666', marginRight: 8 }}>
                              {field.icon}
                            </span>

                            {/* 字段名称 */}
                            <span style={{
                              flex: 1,
                              color: status === 'not_collected' ? '#999' : '#333'
                            }}>
                              {field.label}
                            </span>

                            {/* 字段值 */}
                            <span style={{
                              color: value ? '#333' : '#ccc',
                              fontSize: 12,
                              maxWidth: 150,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              textAlign: 'right'
                            }}>
                              {value || statusDisplay.text}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  )
                ))}

                {/* 物品明细（如果有物品） */}
                {(confirmedItems.length > 0 || fieldsStatus.items?.list?.length > 0) && (
                  <div className="checklist-section" style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>物品明细</div>
                    <div style={{
                      maxHeight: 150,
                      overflowY: 'auto',
                      background: '#fafafa',
                      borderRadius: 4,
                      padding: 8
                    }}>
                      {(confirmedItems.length > 0 ? confirmedItems : fieldsStatus.items?.list || []).map((item, idx) => (
                        <div key={idx} style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          padding: '4px 0',
                          fontSize: 12
                        }}>
                          <span>{item.name_ja || item.name}</span>
                          <Tag color="blue" size="small">×{item.count || 1}</Tag>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 完成进度 */}
                <div style={{ marginTop: 16, padding: '12px', background: '#f5f5f5', borderRadius: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span>收集进度</span>
                    <span>{Math.round((completion.completion_rate || 0) * 100)}%</span>
                  </div>
                  <Progress percent={Math.round((completion.completion_rate || 0) * 100)} strokeColor="#6366f1" />
                </div>

                {/* 状态图例 */}
                <div style={{
                  marginTop: 12,
                  display: 'flex',
                  justifyContent: 'center',
                  gap: 16,
                  fontSize: 11,
                  color: '#999'
                }}>
                  <span><CheckCircleOutlined style={{ color: '#52c41a' }} /> 已收集</span>
                  <span><ClockCircleOutlined style={{ color: '#faad14' }} /> 待回答</span>
                  <span><MinusCircleOutlined style={{ color: '#d9d9d9' }} /> 未收集</span>
                </div>
              </>
            )
          })()}
        </div>
      </Modal>

    </Layout>
  )
}

export default App
