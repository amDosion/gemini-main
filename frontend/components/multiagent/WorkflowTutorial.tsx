/**
 * Workflow Tutorial Component
 * 
 * Interactive tutorial to guide new users through the workflow editor.
 */

import React, { useState, useEffect } from 'react';
import { X, ChevronLeft, ChevronRight, Check } from 'lucide-react';

interface TutorialStep {
  title: string;
  description: string;
  target?: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
  action?: string;
}

const tutorialSteps: TutorialStep[] = [
  {
    title: '欢迎使用工作流编辑器',
    description: '让我们通过简短的教程来了解如何创建和管理多智能体工作流。',
  },
  {
    title: '组件库',
    description: '左侧是组件库，包含 9 种不同类型的节点。您可以拖拽这些节点到画布上。',
    target: 'component-library',
    position: 'right',
    action: '尝试拖拽一个"开始节点"到画布',
  },
  {
    title: '连接节点',
    description: '将鼠标悬停在节点上，您会看到蓝色的连接点。拖拽连接点可以连接两个节点。',
    target: 'canvas',
    position: 'top',
    action: '连接两个节点',
  },
  {
    title: '编辑节点属性',
    description: '点击节点可以打开属性面板，在这里您可以编辑节点的标签、描述和配置。',
    target: 'canvas',
    position: 'top',
    action: '点击一个节点',
  },
  {
    title: '执行工作流',
    description: '点击顶部的"执行工作流"按钮来运行您的工作流。执行状态会实时显示在节点上。',
    target: 'toolbar',
    position: 'bottom',
  },
  {
    title: '查看日志',
    description: '点击"显示日志"按钮可以查看工作流的执行日志，帮助您调试和监控。',
    target: 'toolbar',
    position: 'bottom',
  },
  {
    title: '保存和加载模板',
    description: '您可以将工作流保存为模板，方便以后重复使用。也可以加载预设的模板快速开始。',
    target: 'toolbar',
    position: 'bottom',
  },
  {
    title: '快捷键',
    description: '使用 Ctrl+Z/Ctrl+Y 撤销/重做，Ctrl+E 导出，Ctrl+I 导入。按 Ctrl+/ 查看所有快捷键。',
  },
  {
    title: '完成！',
    description: '您已经掌握了基础操作。现在可以开始创建您的第一个工作流了！',
  },
];

interface WorkflowTutorialProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete?: () => void;
}

export const WorkflowTutorial: React.FC<WorkflowTutorialProps> = ({
  isOpen,
  onClose,
  onComplete,
}) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [isCompleted, setIsCompleted] = useState(false);

  const step = tutorialSteps[currentStep];
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === tutorialSteps.length - 1;

  useEffect(() => {
    // Check if tutorial has been completed before
    const completed = localStorage.getItem('workflow-tutorial-completed');
    if (completed) {
      setIsCompleted(true);
    }
  }, []);

  const handleNext = () => {
    if (isLastStep) {
      handleComplete();
    } else {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handlePrevious = () => {
    if (!isFirstStep) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleComplete = () => {
    localStorage.setItem('workflow-tutorial-completed', 'true');
    setIsCompleted(true);
    onComplete?.();
    onClose();
  };

  const handleSkip = () => {
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-500 to-blue-600 text-white p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold">{step.title}</h2>
              <p className="text-blue-100 text-sm mt-1">
                步骤 {currentStep + 1} / {tutorialSteps.length}
              </p>
            </div>
            <button
              onClick={handleSkip}
              className="text-white hover:text-blue-100 transition-colors"
            >
              <X size={24} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          <p className="text-gray-700 text-lg leading-relaxed mb-4">
            {step.description}
          </p>

          {step.action && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
              <p className="text-sm text-blue-800">
                <span className="font-semibold">💡 尝试：</span> {step.action}
              </p>
            </div>
          )}

          {/* Progress Bar */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-2">
              {tutorialSteps.map((_, index) => (
                <div
                  key={index}
                  className={`
                    flex-1 h-2 rounded-full transition-colors
                    ${index <= currentStep ? 'bg-blue-500' : 'bg-gray-200'}
                  `}
                />
              ))}
            </div>
          </div>

          {/* Navigation */}
          <div className="flex items-center justify-between">
            <button
              onClick={handlePrevious}
              disabled={isFirstStep}
              className="
                px-4 py-2 text-sm font-medium
                bg-gray-100 hover:bg-gray-200
                text-gray-700 rounded-lg
                transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed
                flex items-center gap-2
              "
            >
              <ChevronLeft size={16} />
              上一步
            </button>

            <button
              onClick={handleSkip}
              className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              跳过教程
            </button>

            <button
              onClick={handleNext}
              className="
                px-4 py-2 text-sm font-medium
                bg-blue-500 hover:bg-blue-600
                text-white rounded-lg
                transition-colors
                flex items-center gap-2
              "
            >
              {isLastStep ? (
                <>
                  完成
                  <Check size={16} />
                </>
              ) : (
                <>
                  下一步
                  <ChevronRight size={16} />
                </>
              )}
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-3 border-t border-gray-200">
          <p className="text-xs text-gray-500 text-center">
            您可以随时通过点击工具栏的"帮助"按钮重新查看此教程
          </p>
        </div>
      </div>
    </div>
  );
};

// Tutorial trigger button
export const TutorialButton: React.FC<{ onClick: () => void }> = ({ onClick }) => {
  return (
    <button
      onClick={onClick}
      className="
        px-3 py-1.5 text-xs font-medium
        bg-white hover:bg-gray-50
        border border-gray-300 text-gray-700
        rounded transition-colors
        flex items-center gap-1
      "
    >
      <span>❓</span>
      帮助
    </button>
  );
};

export default WorkflowTutorial;
