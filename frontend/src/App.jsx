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
  UserOutlined, CalendarOutlined, InboxOutlined
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

  // 打字效果队列
  const textQueueRef = useRef([])
  const isTypingRef = useRef(false)

  // 上次的快捷选项（用于避免重复显示）
  const lastOptionsRef = useRef([])

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
        if (data.ui_component) setUiComponent(data.ui_component)
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

  // 上传图片
  const handleUploadImage = useCallback(() => {
    setShowPrivacyModal(true)
  }, [])

  // 确认隐私协议并上传
  const confirmPrivacyAndUpload = useCallback(async () => {
    setShowPrivacyModal(false)
    // 不在对话中显示上传图片消息
    setIsRecognizing(true)
    setRecognitionStep(0)

    // 模拟识别步骤
    for (let step = 1; step <= 4; step++) {
      await new Promise(r => setTimeout(r, 800))
      setRecognitionStep(step)
    }

    // 模拟识别结果 (实际应调用后端)
    const mockItems = [
      { id: 1, name: '衣装ケース', name_ja: '衣装ケース', category: '衣類・寝具', count: 1, note: '备注内容' },
      { id: 2, name: 'タンス類', name_ja: 'タンス類', category: '衣類・寝具', count: 1 },
      { id: 3, name: '乾燥機', name_ja: '乾燥機', category: '家电', count: 1 },
      { id: 4, name: 'エアコン', name_ja: 'エアコン', category: '家电', count: 2 },
      { id: 5, name: 'L 标准纸箱', name_ja: 'ダンボール', category: 'ダンボール', count: 12 }
    ]

    wsRef.current?.send(JSON.stringify({
      type: 'image_uploaded',
      image_id: 'mock_image_' + Date.now(),
      items: mockItems
    }))

    setPendingItems(mockItems)
    setIsRecognizing(false)
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

  // 渲染地址验证卡片
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

        {/* 待确认的物品卡片（确认后会嵌入消息流，这里只显示未确认的） */}
        {pendingItems.length > 0 && !isRecognizing && (
          <div className="message-wrapper assistant">
            <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
            {renderRecognitionResult()}
          </div>
        )}

        {isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
          <div className="message-wrapper assistant">
            <Avatar className="avatar" style={{ backgroundColor: '#6366f1' }}>E</Avatar>
            <Spin indicator={<LoadingOutlined />} />
          </div>
        )}

        {/* Quick Options - 在聊天流中 (物品识别进行中或待确认时不显示) */}
        {!pendingItems.length && !isRecognizing && renderQuickOptions()}

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

      {/* Item List Modal */}
      <Modal
        title="搬家清单"
        open={showItemListModal}
        onCancel={() => setShowItemListModal(false)}
        footer={null}
        width={400}
      >
        <div className="checklist-modal">
          {/* 已收集的信息 */}
          <div className="checklist-section">
            <h4>已收集信息</h4>
            <List
              size="small"
              dataSource={[
                { label: '搬家人数', value: fieldsStatus.people_count?.value || fieldsStatus.people_count, icon: <UserOutlined /> },
                {
                  label: '搬出地址',
                  value: (() => {
                    const addr = fieldsStatus.from_address
                    if (!addr) return null
                    let display = addr.value || ''
                    if (addr.postal_code) display = `〒${addr.postal_code} ${display}`.trim()
                    if (addr.building_type) display += ` (${addr.building_type})`
                    return display || null
                  })(),
                  icon: <EnvironmentOutlined />
                },
                {
                  label: '搬入地址',
                  value: (() => {
                    const addr = fieldsStatus.to_address
                    if (!addr) return null
                    let display = addr.value || ''
                    if (addr.building_type) display += ` (${addr.building_type})`
                    return display || null
                  })(),
                  icon: <EnvironmentOutlined />
                },
                {
                  label: '搬家日期',
                  value: (() => {
                    const date = fieldsStatus.move_date
                    if (!date) return null
                    let display = date.value || ''
                    if (date.time_slot) display += ` ${date.time_slot}`
                    return display || null
                  })(),
                  icon: <CalendarOutlined />
                },
                {
                  label: '搬出楼层',
                  value: (() => {
                    const floor = fieldsStatus.from_floor_elevator
                    if (!floor || !floor.floor) return null
                    let display = `${floor.floor}楼`
                    if (floor.has_elevator === true) display += '（有电梯）'
                    else if (floor.has_elevator === false) display += '（无电梯）'
                    else if (floor.has_elevator) display += `（${floor.has_elevator}）`
                    return display
                  })(),
                  icon: <HomeOutlined />
                },
                {
                  label: '搬入楼层',
                  value: (() => {
                    const floor = fieldsStatus.to_floor_elevator
                    if (!floor || !floor.floor) return null
                    let display = `${floor.floor}楼`
                    if (floor.has_elevator === true) display += '（有电梯）'
                    else if (floor.has_elevator === false) display += '（无电梯）'
                    else if (floor.has_elevator) display += `（${floor.has_elevator}）`
                    return display
                  })(),
                  icon: <HomeOutlined />
                },
                { label: '打包服务', value: fieldsStatus.packing_service, icon: <InboxOutlined /> },
                {
                  label: '特殊注意',
                  value: fieldsStatus.special_notes?.length > 0 ? fieldsStatus.special_notes.join('、') : null,
                  icon: <InboxOutlined />
                },
              ].filter(item => item.value)}
              renderItem={item => (
                <List.Item>
                  <List.Item.Meta
                    avatar={item.icon}
                    title={item.label}
                    description={typeof item.value === 'object' ? JSON.stringify(item.value) : item.value}
                  />
                </List.Item>
              )}
              locale={{ emptyText: '暂无收集信息' }}
            />
          </div>

          {/* 物品清单 */}
          <div className="checklist-section" style={{ marginTop: 16 }}>
            <h4>物品清单</h4>
            {confirmedItems.length === 0 && (!fieldsStatus.items?.list || fieldsStatus.items.list.length === 0) ? (
              <p style={{ textAlign: 'center', color: '#999', padding: '16px 0' }}>暂无物品</p>
            ) : (
              <List
                size="small"
                dataSource={confirmedItems.length > 0 ? confirmedItems : (fieldsStatus.items?.list || [])}
                renderItem={item => (
                  <List.Item>
                    <span>{item.name_ja || item.name}</span>
                    <Tag color="blue">×{item.count || 1}</Tag>
                  </List.Item>
                )}
              />
            )}
          </div>

          {/* 完成进度 */}
          <div style={{ marginTop: 16, padding: '12px', background: '#f5f5f5', borderRadius: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span>收集进度</span>
              <span>{Math.round((completion.completion_rate || 0) * 100)}%</span>
            </div>
            <Progress percent={Math.round((completion.completion_rate || 0) * 100)} strokeColor="#6366f1" />
          </div>
        </div>
      </Modal>

    </Layout>
  )
}

export default App
