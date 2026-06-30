"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { env } from "@/config/env";

interface Question {
  id: string;
  order_index: number;
  question_text: string;
  input_type: string;
  options: any;
}

export default function DecidePage() {
  const { id } = useParams() as { id: string };
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [decisionTitle, setDecisionTitle] = useState("");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [category, setCategory] = useState("laptop");
  
  // Stores answer values mapped by question_id
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currency, setCurrency] = useState("usd");

  useEffect(() => {
    document.documentElement.classList.add("dark");
    fetchDecision();
  }, [id]);

  const fetchDecision = async () => {
    try {
      const guestId = localStorage.getItem("nexus_guest_id") || "";
      const response = await fetch(`${env.NEXT_PUBLIC_API_URL}/api/decisions/${id}`, {
        headers: {
          "X-Guest-ID": guestId,
        },
      });

      if (!response.ok) {
        throw new Error("Failed to load decision session details.");
      }

      const data = await response.json();
      setDecisionTitle(data.title);
      setQuestions(data.questions);
      setCurrency(data.currency || "usd");
      setCategory(data.category || "laptop");

      // Pre-populate answers with defaults from options if available
      const initialAnswers: Record<string, any> = {};
      data.questions.forEach((q: Question) => {
        // Look if user already answered
        const preAnswer = data.answers.find((a: any) => a.question_id === q.id);
        if (preAnswer) {
          initialAnswers[q.id] = preAnswer.selected_value.value;
        } else {
          // Fallback to template default
          initialAnswers[q.id] = q.options?.default ?? (q.input_type === "slider" ? 3 : "");
        }
      });
      setAnswers(initialAnswers);
      setLoading(false);
    } catch (err: any) {
      toast.error(err.message || "Could not connect to the backend server.");
      setLoading(false);
    }
  };

  const handleValueChange = (questionId: string, val: any) => {
    setAnswers((prev) => ({
      ...prev,
      [questionId]: val,
    }));
  };

  const getVisibleQuestions = (questionsList: Question[], currentAnswers: Record<string, any>): Question[] => {
    return questionsList.filter(q => {
      const dep = q.options?.depends_on;
      if (!dep) return true;
      
      const parentQ = questionsList.find(parent => parent.options?.maps_to === dep.maps_to);
      if (!parentQ) return true;
      
      const parentAnswer = currentAnswers[parentQ.id];
      return parentAnswer === dep.value;
    });
  };

  const visibleQuestions = getVisibleQuestions(questions, answers);

  useEffect(() => {
    if (visibleQuestions.length > 0 && currentIndex >= visibleQuestions.length) {
      setCurrentIndex(visibleQuestions.length - 1);
    }
  }, [answers, visibleQuestions.length, currentIndex]);

  const handleNext = () => {
    if (currentIndex < visibleQuestions.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      submitAllAnswers();
    }
  };

  const handleBack = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  const submitAllAnswers = async () => {
    setSubmitLoading(true);
    try {
      const guestId = localStorage.getItem("nexus_guest_id") || "";
      const visibleQs = getVisibleQuestions(questions, answers);
      const formattedAnswers = visibleQs.map((q) => ({
        question_id: q.id,
        selected_value: { value: answers[q.id] }
      }));

      const response = await fetch(`${env.NEXT_PUBLIC_API_URL}/api/decisions/${id}/answers`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Guest-ID": guestId,
        },
        body: JSON.stringify({ answers: formattedAnswers }),
      });

      if (!response.ok) {
        throw new Error("Failed to save your answers.");
      }

      toast.success("All answers saved!");
      // Proceed to evaluation results page
      router.push(`/decide/${id}/results`);
    } catch (err: any) {
      toast.error(err.message || "Failed to commit answers.");
      setSubmitLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center flex-col gap-4">
        <span className="w-12 h-12 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
        <p className="text-slate-400 font-medium">Assembling decision wizard...</p>
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center flex-col gap-4">
        <p className="text-red-400 font-bold">Error: No questions found for this decision.</p>
        <button onClick={() => router.push("/")} className="px-4 py-2 bg-slate-800 rounded">
          Back to Home
        </button>
      </div>
    );
  }

  const currentQuestion = visibleQuestions[currentIndex];
  if (!currentQuestion) return null;
  const progressPercent = Math.round(((currentIndex + 1) / visibleQuestions.length) * 100);

  // Helper labels for slider priorities
  const getSliderLabel = (val: number) => {
    switch (val) {
      case 0: return "0 — Not Important (Ignore)";
      case 1: return "1 — Very Low Priority";
      case 2: return "2 — Low Priority";
      case 3: return "3 — Medium Priority";
      case 4: return "4 — High Priority";
      case 5: return "5 — Critical Priority";
      default: return val.toString();
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.06),transparent_40%)] pointer-events-none" />

      {/* Header */}
      <header className="max-w-5xl mx-auto w-full px-6 py-6 flex items-center justify-between border-b border-slate-900 bg-slate-950/80 backdrop-blur-sm sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <button 
            onClick={() => router.push("/")}
            className="w-8 h-8 rounded-lg border border-slate-800 flex items-center justify-center hover:bg-slate-900 text-slate-400 hover:text-white transition-all"
          >
            &larr;
          </button>
          <div>
            <h2 className="font-accent font-bold text-white tracking-tight">{decisionTitle || "Requirements Mapping"}</h2>
            <p className="text-xs text-slate-400">Step {currentIndex + 1} of {visibleQuestions.length}</p>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="flex items-center gap-3 w-40 md:w-60">
          <div className="flex-grow bg-slate-850 h-2 rounded-full overflow-hidden border border-slate-800">
            <div 
              className="bg-gradient-to-r from-indigo-500 to-purple-600 h-full rounded-full transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <span className="text-xs text-slate-400 font-bold">{progressPercent}%</span>
        </div>
      </header>

      {/* Main wizard card container */}
      <main className="max-w-2xl mx-auto w-full px-6 py-12 flex-grow flex items-center justify-center z-10">
        <div className="w-full p-[1px] rounded-2xl bg-gradient-to-br from-slate-800 via-slate-900 to-slate-850 shadow-2xl border border-slate-800/80 backdrop-blur-xl">
          <div className="p-8 bg-slate-950/95 rounded-[14px] flex flex-col justify-between min-h-[380px]">
            
            {/* Bottom Actions or Question Card */}
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1 rounded">
                Category: {category ? category.charAt(0).toUpperCase() + category.slice(1) : ""}
              </span>
              
              <h2 className="text-xl md:text-2xl font-bold text-white mt-6 mb-8 leading-snug">
                {currentQuestion.question_text}
              </h2>

              {/* Dynamic Input Renderers */}
              <div className="my-6">
                
                {/* Budget Range Renderer */}
                {currentQuestion.input_type === "budget_range" && (
                  <div className="flex flex-col gap-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-400">Select Limit:</span>
                      <span className="text-2xl font-extrabold text-white bg-slate-900 border border-slate-800 px-4 py-1.5 rounded-lg">
                        {currency === "inr" ? "₹" : "$"}{(answers[currentQuestion.id] !== undefined ? answers[currentQuestion.id] : (currentQuestion.options?.default ?? 1500)).toLocaleString()}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={currentQuestion.options?.min || 300}
                      max={currentQuestion.options?.max || 5000}
                      step={currentQuestion.options?.step || 100}
                      value={answers[currentQuestion.id] !== undefined ? answers[currentQuestion.id] : (currentQuestion.options?.default ?? 1500)}
                      onChange={(e) => handleValueChange(currentQuestion.id, Number(e.target.value))}
                      className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                    />
                    <div className="flex justify-between text-xs text-slate-500">
                      <span>{currency === "inr" ? "₹" : "$"}{(currentQuestion.options?.min || 300).toLocaleString()}</span>
                      <span>{currency === "inr" ? "₹" : "$"}{(currentQuestion.options?.max || 5000).toLocaleString()}</span>
                    </div>
                  </div>
                )}

                {/* Single Choice / Selection Buttons */}
                {currentQuestion.input_type === "single_choice" && (
                  <div className="grid grid-cols-2 gap-3">
                    {currentQuestion.options?.choices?.map((choice: any) => {
                      const isSelected = answers[currentQuestion.id] === choice;
                      return (
                        <button
                          key={choice}
                          type="button"
                          onClick={() => handleValueChange(currentQuestion.id, choice)}
                          className={`px-4 py-4 rounded-xl border text-base font-bold transition-all text-center flex items-center justify-center gap-2 hover:scale-[1.01] active:scale-[0.99] ${
                            isSelected
                              ? "bg-gradient-to-tr from-indigo-500 to-purple-600 border-indigo-400 text-white shadow-lg shadow-indigo-500/20"
                              : "border-slate-800 bg-slate-900/40 text-slate-300 hover:bg-slate-900/80 hover:text-white"
                          }`}
                        >
                          {choice}{currentQuestion.options?.unit ? ` ${currentQuestion.options.unit}` : ""}
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Slider (Weight Priority Scale) */}
                {currentQuestion.input_type === "slider" && (
                  <div className="flex flex-col gap-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-slate-400">Level of Importance:</span>
                      <span className="text-sm font-bold text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-3 py-1.5 rounded-full">
                        {getSliderLabel(answers[currentQuestion.id] ?? 3)}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={5}
                      step={1}
                      value={answers[currentQuestion.id] ?? 3}
                      onChange={(e) => handleValueChange(currentQuestion.id, Number(e.target.value))}
                      className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                    />
                    <div className="flex justify-between text-xs text-slate-500 px-1">
                      <span>0 (Ignore)</span>
                      <span>1</span>
                      <span>2</span>
                      <span>3</span>
                      <span>4</span>
                      <span>5 (Critical)</span>
                    </div>
                  </div>
                )}

              </div>
            </div>

            {/* Bottom Actions */}
            <div className="flex items-center justify-between border-t border-slate-900 pt-6 mt-8">
              <button
                type="button"
                onClick={handleBack}
                disabled={currentIndex === 0 || submitLoading}
                className="px-5 py-2.5 rounded-lg border border-slate-800 hover:bg-slate-900 text-slate-400 hover:text-white transition-all disabled:opacity-30 disabled:pointer-events-none"
              >
                &larr; Back
              </button>

              <button
                type="button"
                onClick={handleNext}
                disabled={submitLoading}
                className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white font-bold transition-all flex items-center gap-2 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none"
              >
                {submitLoading ? (
                  <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : currentIndex === visibleQuestions.length - 1 ? (
                  "Calculate Recommendation"
                ) : (
                  "Continue"
                )}
              </button>
            </div>

          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-4 border-t border-slate-900 text-center text-xs text-slate-650 bg-slate-950/20">
        Answers are processed locally using deterministic MCDA mathematical matrices.
      </footer>
    </div>
  );
}
