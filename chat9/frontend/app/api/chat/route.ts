import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
    const { messages } = await req.json()
    const lastMessage = messages[messages.length - 1]

    const response = await fetch(`${process.env.NEXT_PUBLIC_CHATBOT_URL}/api/chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content: lastMessage.content }),
    })

    if (!response.ok) {
        console.error('Backend response:', await response.text())
        return NextResponse.json({ error: 'Failed to fetch from backend' }, { status: 500 })
    }

    const data = await response.json()
    return NextResponse.json(data)
}
