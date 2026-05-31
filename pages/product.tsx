"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { useAuth } from "@clerk/nextjs";
import { Protect, PricingTable, UserButton } from "@clerk/nextjs";

function NoteExtractor() {
  const { getToken } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState<string>("");
  const [loading, setLoading] = useState(false);

  async function handleUpload() {
    if (!file) return;

    setLoading(true);
    setText("");

    try {
      const jwt = await getToken();

      if (!jwt) {
        setText("Authentication required");
        return;
      }

      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${jwt}`,
        },
        body: formData,
      });

      if (!res.ok || !res.body) {
        const errorText = await res.text();
        throw new Error(errorText || `Request failed with status ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        setText(buffer);
      }
    } catch (error) {
      setText(`Error: ${String(error)}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container mx-auto px-4 py-12">
      <header className="text-center mb-12">
        <h1 className="text-5xl font-bold text-slate-800 mb-4">
          NoteVision AI
        </h1>

        <p className="text-slate-600 text-lg">
          AI-powered handwritten note and PDF digitization
        </p>
      </header>

      <div className="max-w-3xl mx-auto">
        <div className="bg-white rounded-3xl shadow-xl border border-slate-200 p-8">
          <div className="mb-6 rounded-2xl border-2 border-dashed border-slate-300 p-8 text-center bg-slate-50">
            <input
              id="file-upload"
              type="file"
              accept="image/*,.pdf,application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="hidden"
            />

            <label
              htmlFor="file-upload"
              className="inline-block cursor-pointer bg-slate-700 hover:bg-slate-800 text-white font-medium py-3 px-6 rounded-xl transition-all shadow-sm"
            >
              Upload Image or PDF
            </label>

            <p className="mt-4 text-slate-600">
              {file ? file.name : "No file selected"}
            </p>
          </div>

          <button
            onClick={handleUpload}
            disabled={!file || loading}
            className="w-full bg-slate-800 hover:bg-slate-900 text-white font-bold py-4 px-8 rounded-2xl text-lg transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Extracting text..." : "Extract Text"}
          </button>

          {text && (
            <div className="mt-8 markdown-content text-slate-700">
              <h2 className="text-2xl font-bold mb-4 text-slate-800">
                Extracted Text
              </h2>

              <div className="bg-slate-50 rounded-2xl p-6 whitespace-pre-wrap border border-slate-200">
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                  {text}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Product() {
  return (
    <main className="min-h-screen bg-slate-50">
      <div className="absolute top-4 right-4 bg-white rounded-xl px-3 py-2 border border-slate-200 shadow-sm">
        <UserButton showName={true} />
      </div>

      <Protect
        plan="premium_subscription"
        fallback={
          <div className="container mx-auto px-4 py-12">
            <header className="text-center mb-12">
              <h1 className="text-5xl font-bold text-slate-800 mb-4">
                NoteVision AI Premium
              </h1>

              <p className="text-slate-600 text-lg mb-8">
                Unlock unlimited handwritten note and PDF digitization with
                AI-powered OCR.
              </p>
            </header>

            <div className="max-w-4xl mx-auto bg-white rounded-3xl border border-slate-200 shadow-xl p-6">
              <PricingTable />
            </div>
          </div>
        }
      >
        <NoteExtractor />
      </Protect>
    </main>
  );
}